"""Offline, source-grouped quality protocol preparation; no inference or labels.

Freezing records operator-declared sample membership, never human acceptance.
Hashes detect stale evidence and accidental receipt edits, not human identity.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

COMMANDS = ('quality-preview', 'quality-freeze', 'quality-check')
SCHEMA = 'f1.quality_protocol.v1'
RECEIPT_SCHEMA = 'f1.quality_protocol_receipt.v1'
IDENTITY_KEYS = ('id', 'year', 'country_name', 'session_name', 'event_date', 'session_key', 'meeting_key')
MAX_DOCUMENT_BYTES = 2_000_000
PROTOCOL_FIELDS = {'schema_version', 'protocol_id', 'event_identity', 'rubric', 'split_assignment', 'cases'}


def _text(value, field):
    if (not isinstance(value, str) or not value.strip() or value != value.strip()
            or len(value) > 500 or any(ord(char) < 32 for char in value)):
        raise ValueError(field + ' must be explicit bounded text')


def _slug(value, field):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,99}', value):
        raise ValueError(field + ' must be a bounded lowercase identifier')


def _shape(value, fields, field):
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(field + ' has missing or unsupported fields')


def _load(path):
    if not path.is_file() or path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError('A bounded workspace JSON file is required')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Finite JSON is required')))


def _workspace(root):
    from .core import ROOT, safe_relative, validate_config
    root = Path(ROOT if root is None else root).resolve()
    config_path = safe_relative('config/event.json', root=root)
    config = validate_config(_load(config_path), root=root)
    return root, config, {key: config[key] for key in IDENTITY_KEYS}


def _request_path(path, root):
    from .core import safe_relative
    if path is None:
        raise ValueError('This command requires --request with a workspace JSON file')
    target = safe_relative(path, root=root)
    if not target.is_file():
        raise ValueError('The request is not a workspace file')
    return target


def _binding(item, root):
    from .core import digest, safe_relative
    _shape(item, {'path', 'sha256'}, 'evidence binding')
    path, sha = item['path'], item['sha256']
    if (not isinstance(path, str) or not path or Path(path).is_absolute()
            or '..' in Path(path).parts or Path(path).as_posix() != path
            or not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{64}', sha)):
        raise ValueError('Invalid canonical workspace path/hash binding')
    target = safe_relative(path, root=root)
    if target.relative_to(root).as_posix() != path:
        raise ValueError('Evidence requires canonical paths without symlink aliases')
    if not target.is_file() or digest(target) != sha:
        raise ValueError('Stale or missing evidence binding: ' + path)


def validate_protocol(document, *, root=None):
    """Validate exact event, current evidence, and declared split separation."""
    root, _, identity = _workspace(root)
    _shape(document, PROTOCOL_FIELDS, 'quality protocol')
    if document['schema_version'] != SCHEMA:
        raise ValueError('Unsupported quality protocol schema')
    _slug(document['protocol_id'], 'protocol_id')
    # Equality alone treats bool as an integer; compare serialized types too.
    if _canonical(document['event_identity']) != _canonical(identity):
        raise ValueError('Quality protocol does not match the selected exact event identity')
    rubric = document['rubric']
    _shape(rubric, {'version', 'path', 'sha256'}, 'rubric')
    _text(rubric['version'], 'rubric version')
    _binding({key: rubric[key] for key in ('path', 'sha256')}, root)
    declaration = document['split_assignment']
    _shape(declaration, {'kind', 'reference'}, 'split assignment')
    if declaration['kind'] != 'operator_declared':
        raise ValueError('Split assignment must be operator_declared, not inferred')
    _text(declaration['reference'], 'split assignment reference')
    cases = document['cases']
    if not isinstance(cases, list) or not cases or len(cases) > 1000:
        raise ValueError('Protocol requires 1 to 1000 explicitly declared cases')
    ids, groups, evidence_paths, evidence_hashes = set(), {}, {}, {}
    counts = Counter()
    for case in cases:
        _shape(case, {'case_id', 'split', 'source_group_ids', 'evidence'}, 'case')
        _slug(case['case_id'], 'case_id')
        if case['case_id'] in ids:
            raise ValueError('Duplicate case_id')
        ids.add(case['case_id'])
        split = case['split']
        if not isinstance(split, str) or split not in {'development', 'held_out'}:
            raise ValueError('Each split must explicitly be development or held_out')
        counts[split] += 1
        source_groups = case['source_group_ids']
        if not isinstance(source_groups, list) or not source_groups:
            raise ValueError('Each case requires source_group_ids')
        seen_groups = set()
        for group in source_groups:
            _slug(group, 'source_group_id')
            if group in seen_groups:
                raise ValueError('Duplicate source_group_id in a case')
            seen_groups.add(group)
            if group in groups and groups[group] != split:
                raise ValueError('Source-group split leakage: ' + group)
            groups[group] = split
        bindings = case['evidence']
        if not isinstance(bindings, list) or not bindings:
            raise ValueError('Each case requires current evidence bindings')
        seen_paths = set()
        for binding in bindings:
            _binding(binding, root)
            path, sha = binding['path'], binding['sha256']
            if path in seen_paths:
                raise ValueError('Duplicate evidence path within a case')
            seen_paths.add(path)
            for key, index in ((path, evidence_paths), (sha, evidence_hashes)):
                if key in index and index[key] != split:
                    raise ValueError('Evidence path/content split leakage: ' + path)
                index[key] = split
    if set(counts) != {'development', 'held_out'}:
        raise ValueError('Protocol requires both development and held_out cases')
    return {'cases': dict(counts), 'source_groups': len(groups), 'evidence_files': len(evidence_paths)}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _summary(protocol, counts, status):
    return {'schema_version': 'f1.quality_protocol_status.v1', 'protocol_id': protocol['protocol_id'],
            'event_identity': protocol['event_identity'], 'status': status,
            'rubric_version': protocol['rubric']['version'], 'sample': counts,
            'split_assignment': 'operator_declared', 'provider_calls': False,
            'human_evidence_status': 'not_assessed', 'human_acceptance': 'not_inferred',
            'held_out_execution': 'not_performed', 'quality_parity': 'not_established',
            'model_promotion': False,
            'pending': ['real human-reviewed labels/preferences', 'actual held-out evaluation',
                        'explicit human model-promotion decision']}


def preview_protocol(request, *, root=None):
    from .core import digest
    root, _, _ = _workspace(root)
    path = _request_path(request, root)
    protocol = _load(path)
    counts = validate_protocol(protocol, root=root)
    return {**_summary(protocol, counts, 'validated_preview'),
            'request_binding': {'path': path.relative_to(root).as_posix(), 'sha256': digest(path)},
            'writes_performed': False}


def freeze_protocol(request, *, root=None):
    from .core import digest, ensure_space, now, safe_relative
    root, config, _ = _workspace(root)
    path = _request_path(request, root)
    request_sha = digest(path)
    protocol = _load(path)
    counts = validate_protocol(protocol, root=root)
    receipt = {'schema_version': RECEIPT_SCHEMA, 'frozen_at': now(), 'protocol': protocol,
               'request_binding': {'path': path.relative_to(root).as_posix(), 'sha256': request_sha},
               'config_binding': {'path': 'config/event.json', 'sha256': digest(root / 'config/event.json')}}
    receipt['record_sha256'] = _hash(receipt)
    encoded = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n'
    if len(encoded.encode('utf-8')) > MAX_DOCUMENT_BYTES:
        raise ValueError('Frozen receipt exceeds local document limit')
    relative = 'runs/quality-protocols/' + protocol['protocol_id'] + '.json'
    target = safe_relative(relative, root=root)
    if target.relative_to(root).as_posix() != relative:
        raise ValueError('Frozen receipts require canonical paths without symlink aliases')
    if target.exists():
        raise ValueError('Protocol identifier already frozen; use a new protocol_id')
    ensure_space(len(encoded.encode('utf-8')), root=root, reserve=config['reserve_bytes'])
    target.parent.mkdir(parents=True, exist_ok=True)
    # Save complete bytes first, then publish exclusively; no truncated receipt
    # becomes visible if interrupted during writing or a competing freeze wins.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        _binding(receipt['request_binding'], root)
        _binding(receipt['config_binding'], root)
        validate_protocol(protocol, root=root)
        try:
            os.link(temporary, target)
        except FileExistsError:
            raise ValueError('Protocol identifier already frozen; use a new protocol_id') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {**_summary(protocol, counts, 'frozen'), 'receipt_path': target.relative_to(root).as_posix(),
            'sha256': digest(target), 'record_sha256': receipt['record_sha256']}


def check_protocol(request, *, root=None):
    from .core import digest, safe_relative
    root, _, _ = _workspace(root)
    path = _request_path(request, root)
    receipt = _load(path)
    _shape(receipt, {'schema_version', 'frozen_at', 'protocol', 'request_binding',
                     'config_binding', 'record_sha256'}, 'frozen receipt')
    if receipt['schema_version'] != RECEIPT_SCHEMA:
        raise ValueError('Unsupported frozen quality protocol receipt')
    _text(receipt['frozen_at'], 'frozen_at')
    payload = {key: value for key, value in receipt.items() if key != 'record_sha256'}
    if receipt['record_sha256'] != _hash(payload):
        raise ValueError('Corrupt frozen receipt hash')
    _binding(receipt['request_binding'], root)
    _binding(receipt['config_binding'], root)
    if receipt['config_binding']['path'] != 'config/event.json':
        raise ValueError('Frozen receipt must bind selected event config')
    protocol = receipt['protocol']
    counts = validate_protocol(protocol, root=root)
    expected_path = 'runs/quality-protocols/' + protocol['protocol_id'] + '.json'
    if path.relative_to(root).as_posix() != expected_path:
        raise ValueError('Check requires the canonical frozen receipt path')
    original = _load(safe_relative(receipt['request_binding']['path'], root=root))
    if _canonical(original) != _canonical(protocol):
        raise ValueError('Frozen protocol does not match its bound request')
    return {**_summary(protocol, counts, 'current_frozen_protocol'), 'receipt_path': expected_path,
            'sha256': digest(path), 'record_sha256': receipt['record_sha256']}


def run(args):
    """Dispatch shared-CLI commands; every operation remains offline."""
    from .core import ROOT
    if getattr(args, 'execute', False):
        raise ValueError('Quality protocol commands cannot execute inference')
    action = {'quality-preview': preview_protocol, 'quality-freeze': freeze_protocol,
              'quality-check': check_protocol}.get(args.command)
    if action is None:
        raise ValueError('Unknown quality protocol command')
    return action(args.request, root=ROOT)
