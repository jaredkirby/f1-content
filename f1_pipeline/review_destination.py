"""Prepare a private mobile review Site from one validated output version.

This offline command never publishes, calls a provider or records human approval.
The generated Site and media stay outside the shared source repository.
"""
from __future__ import annotations

import math
from pathlib import Path
import shutil
from urllib.parse import urlparse

from .core import ROOT, config, digest, now, read_json, safe_relative, write_json
from .validate import QA_BASE_INPUTS, verify_bindings, verify_render_bindings

WEB_CHECKS = {'mobile_layout', 'video_playback', 'video_seek', 'captions_unobscured',
              'annotation_persistence', 'decision_history', 'chat_copy',
              'version_rejection', 'authentication', 'hosted_page_and_media'}

TEMPLATE_ROOT = Path(__file__).with_name('resources')/'mobile-review-site'
TEMPLATE_FILES = (
    'app/api/credential/route.ts', 'app/api/feedback/route.ts',
    'app/api/operator/credential/route.ts', 'app/connect/key-entry.tsx',
    'app/connect/page.tsx', 'app/globals.css', 'app/layout.tsx', 'app/page.tsx',
    'app/review.tsx', 'cloudflare-env.d.ts', 'db/schema.ts', 'lib/bounded-body.ts',
    'lib/credential-box.ts', 'lib/credential-operation.mjs', 'public/favicon.svg', 'scripts/test-credential-box.mjs',
    'scripts/verify-credential.mjs', 'scripts/verify-feedback.mjs',
)


def verify_technical_review(manifest, qa, manifest_sha, event_id):
    """Bind mobile readiness to the same current render inputs and EDL as release QA."""
    if not isinstance(manifest, dict) or manifest.get('event_id') != event_id:
        raise ValueError('Manifest does not match the selected event')
    if not isinstance(qa, dict) or qa.get('status') != 'passed' or qa.get('errors') != []:
        raise ValueError('A passed technical validation is required before Site preparation')
    if qa.get('event_id') != event_id or qa.get('input_hashes', {}).get('outputs/manifest.json') != manifest_sha:
        raise ValueError('Technical validation is stale for this manifest')
    captured = verify_render_bindings(manifest)
    bindings = verify_bindings(qa.get('input_hashes', {}), QA_BASE_INPUTS | set(captured), 'Technical review')
    if any(bindings.get(path) != expected for path, expected in captured.items()):
        raise ValueError('Technical review does not bind the current render inputs')
    plan = safe_relative(manifest.get('edit_plan', 'outputs/edit-plan.json'))
    if (not plan.is_file() or digest(plan) != manifest.get('edit_plan_sha256')
            or qa.get('edit_plan_sha256') != manifest.get('edit_plan_sha256')):
        raise ValueError('Technical edit-plan review is stale')


def prepare_review_site(site_directory):
    requested = Path(site_directory).expanduser()
    if not requested.is_absolute() or not requested.is_dir():
        raise ValueError("Site directory must be an existing absolute directory")
    site = requested.resolve()
    if site == ROOT or site in ROOT.parents or ROOT in site.parents:
        raise ValueError("Keep the independent Site outside the event workspace")
    cfg = config()
    manifest_path = safe_relative('outputs/manifest.json')
    manifest = read_json(manifest_path)
    qa = read_json(safe_relative('outputs/qa.json'))
    manifest_sha = digest(manifest_path)
    verify_technical_review(manifest, qa, manifest_sha, cfg['id'])
    videos = [v for v in manifest.get('videos', []) if v.get('format') == 'vertical']
    if len(videos) != 1:
        raise ValueError("Review exactly one vertical output at a time")
    video = videos[0]
    duration = video.get('duration')
    if type(duration) not in (int, float) or not math.isfinite(duration) or not 0 < duration <= 600:
        raise ValueError("Invalid bounded video duration")
    if video.get('width', 0) <= 0 or video.get('height', 0) <= video['width']:
        raise ValueError("The review output must be vertical")
    if not any(v.get('format') == 'vertical' and v.get('sha256') == video.get('sha256') for v in qa.get('videos', [])):
        raise ValueError("Technical validation does not bind this video")
    sources = {}
    for key in ('path', 'thumbnail', 'script', 'captions'):
        source = safe_relative(video[key])
        expected = video.get('sha256') if key == 'path' else video.get('companion_sha256', {}).get(key)
        if not source.is_file() or not expected or digest(source) != expected:
            raise ValueError("Changed or unbound review asset: " + key)
        if source.stat().st_size > 24 * 1024**2:
            raise ValueError("Review asset exceeds the bounded Site asset size: " + key)
        sources[key] = source
    receipts = []
    for link in video.get('model_runs', []):
        from .feedback import _model_runs
        from .model_evaluation import IDENTITY_KEYS
        _model_runs([link], ROOT, {k: cfg[k] for k in IDENTITY_KEYS})
        if link not in receipts:
            receipts.append(link)
    state = read_json(safe_relative('runs/pilot/pilot-state.json'), {})
    if state:
        if state.get('manifest_sha256') != manifest_sha or state.get('video', {}).get('sha256') != video['sha256']:
            raise ValueError("Pilot state is stale for this output")
        receipt = state.get('reference_receipt')
        if receipt:
            if digest(safe_relative(receipt['path'])) != receipt['sha256']:
                raise ValueError("Pilot model receipt changed")
            link = {'path': receipt['path'], 'sha256': receipt['sha256']}
            if link not in receipts: receipts.append(link)
    operation = {'id': 'not-configured', 'enabled': False, 'persistKeychain': False,
                 'model': 'deepseek/deepseek-v4.1-flash', 'budgetUsd': None,
                 'requestSha256': None, 'requestFileSha256': None}
    active = state.get('active_hosted_candidate', {})
    review_label = state.get('review_label', '01 / REFERENCE')
    authoring_note = state.get('authoring_note', 'A single reference edit, built around the qualifying sector comparison.')
    if (not isinstance(review_label, str) or not review_label.strip() or len(review_label) > 80
            or not isinstance(authoring_note, str) or not authoring_note.strip() or len(authoring_note) > 400):
        raise ValueError('Review label and authoring context must be bounded text')
    authorization = active.get('spending_authorization')
    if authorization:
        authorization_path = safe_relative(authorization['path'])
        if digest(authorization_path) != authorization['sha256']:
            raise ValueError('Changed candidate execution authorization')
        auth = read_json(authorization_path)
        binding = active['request']
        request_path = safe_relative(binding['path'])
        if digest(request_path) != binding['sha256'] or auth.get('request_binding') != binding:
            raise ValueError('Changed authorized candidate request')
        from .hosted_inference import preflight
        preview = preflight(read_json(request_path), budget_usd=auth.get('budget_usd'))
        if (auth.get('source', {}).get('kind') != 'human' or type(auth.get('max_calls')) is not int or auth['max_calls'] != 1
                or auth.get('provider') != preview['provider'] or auth.get('model') != preview['requested_model']
                or preview['cost']['budget_usd'] is None
                or preview['cost']['budget_usd'] < preview['cost']['preflight_ceiling_usd']):
            raise ValueError('A bounded human-authorized candidate run is required')
        operation = {'id': authorization['sha256'][:24] + ':transient-v1', 'enabled': True, 'persistKeychain': False,
                     'model': preview['requested_model'], 'budgetUsd': auth['budget_usd'],
                     'requestSha256': preview['request_sha256'], 'requestFileSha256': binding['sha256']}
    # Validate every source before changing the destination. Preserve starter integration.
    templates = TEMPLATE_ROOT
    missing = [name for name in TEMPLATE_FILES if not (templates/name).is_file()]
    if missing:
        raise ValueError('Packaged review Site templates are missing: ' + ', '.join(missing))
    for target in (site/'app/data/pilot.json', site/'.openai/hosting.json'):
        if site not in target.resolve().parents:
            raise ValueError("Site data destination escapes its checkout")
    for source in templates.rglob('*'):
        if source.is_file() and source.name != 'README.md':
            target = site/source.relative_to(templates)
            if site not in target.resolve().parents:
                raise ValueError("Site template destination escapes its checkout")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    assets = {}
    for key, suffix in (('path', '.mp4'), ('thumbnail', '.jpg'), ('script', '.txt'), ('captions', '.srt')):
        filename = 'pilot-' + digest(sources[key])[:16] + suffix
        target = site/'public/media'/filename
        if site not in target.resolve().parents:
            raise ValueError("Site media destination escapes its checkout")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sources[key], target)
        if digest(target) != digest(sources[key]):
            raise ValueError("Copied review asset failed verification")
        assets[key] = '/media/' + filename
    pilot = {'eventId': cfg['id'], 'eventLabel': f"{cfg['country_name']} · {cfg['session_name']} · {cfg['year']}",
             'title': video['title'], 'format': 'vertical', 'duration': duration,
             'reviewLabel': review_label, 'authoringNote': authoring_note,
             'narration': video.get('narration', 'macOS Samantha narration'),
             'credentialHandoffEnabled': operation['enabled'],
             'width': video['width'], 'height': video['height'], 'version': manifest['run_id'],
             'manifestSha256': manifest_sha, 'videoSha256': video['sha256'], 'modelReceipts': receipts,
             'videoUrl': assets['path'], 'posterUrl': assets['thumbnail'], 'scriptUrl': assets['script'],
             'captionsUrl': assets['captions']}
    write_json(site/'app/data/pilot.json', pilot)
    write_json(site/'app/data/credential-operation.json', operation)
    hosting_path = site/'.openai/hosting.json'
    hosting = read_json(hosting_path, {})
    hosting.update({'d1': 'DB', 'r2': None})
    write_json(hosting_path, hosting)
    result = {'schema_version': 'f1.review_destination.v1', 'prepared_at': now(),
              'status': 'prepared_awaiting_web_checks', 'event_id': cfg['id'],
              'manifest_sha256': manifest_sha, 'video_sha256': video['sha256'],
              'model_receipts': receipts, 'project_id': hosting.get('project_id'),
              'site_directory': str(site), 'url': None, 'browser_checks': None,
              'human_acceptance': 'not_reviewed'}
    write_json(safe_relative('runs/pilot/review-destination.json'), result)
    return result


def review_site_status():
    """Fail closed on missing/stale operator browser and native deployment evidence."""
    try:
        record = read_json(safe_relative('runs/pilot/review-destination.json'), {})
    except (OSError, ValueError):
        return {'status': 'incomplete', 'ready_for_human_review': False,
                'issues': ['Review destination receipt is unreadable.']}
    if not isinstance(record, dict):
        return {'status': 'incomplete', 'ready_for_human_review': False,
                'issues': ['Review destination receipt must be an object.']}
    issues = []
    if not record:
        return {'status': 'missing', 'ready_for_human_review': False,
                'issues': ['Prepare and test a mobile web destination for this output.']}
    try:
        manifest = read_json(safe_relative('outputs/manifest.json'))
        manifest_sha = digest(safe_relative('outputs/manifest.json'))
        event_id = config()['id']
        if manifest.get('event_id') != event_id or record.get('event_id') != event_id or record.get('manifest_sha256') != manifest_sha:
            issues.append('Review destination belongs to a different event or manifest.')
        qa = read_json(safe_relative('outputs/qa.json'), {})
        verify_technical_review(manifest, qa, manifest_sha, event_id)
        video = next(v for v in manifest['videos'] if v.get('format') == 'vertical')
        if record.get('video_sha256') != video.get('sha256') or digest(safe_relative(video['path'])) != video['sha256']:
            issues.append('The reviewed video changed.')
        for key in ('thumbnail', 'script', 'captions'):
            if digest(safe_relative(video[key])) != video.get('companion_sha256', {}).get(key):
                issues.append('A reviewed video companion changed.')
        for receipt in record.get('model_receipts', []):
            if digest(safe_relative(receipt['path'])) != receipt['sha256']:
                issues.append('The model receipt changed.')
        verified = {}
        for key in ('browser_checks', 'deployment_receipt'):
            link = record.get(key)
            if not isinstance(link, dict) or digest(safe_relative(link['path'])) != link['sha256']:
                issues.append('Missing or changed ' + key + '.')
                continue
            verified[key] = read_json(safe_relative(link['path']))
        checks = verified.get('browser_checks', {})
        passed = {c.get('check') for c in checks.get('checks', []) if c.get('status') == 'passed'}
        if (checks.get('manifest_sha256') != manifest_sha or checks.get('video_sha256') != video['sha256']
                or not WEB_CHECKS <= passed):
            issues.append('Current mobile browser checks are incomplete.')
        deployment = verified.get('deployment_receipt', {})
        if (checks.get('site_commit_sha') != deployment.get('commit_sha') or not deployment.get('commit_sha')
                or checks.get('project_id') != record.get('project_id') or checks.get('url') != record.get('url')):
            issues.append('Browser checks do not bind the deployed Site version.')
        url = urlparse(record.get('url') or '')
        if (url.scheme != 'https' or not url.hostname or not url.hostname.endswith('.chatgpt.site')
                or deployment.get('status') != 'succeeded' or deployment.get('url') != record.get('url')
                or deployment.get('project_id') != record.get('project_id')
                or deployment.get('audience') != 'owner_private'
                or not deployment.get('version_id') or not deployment.get('id')):
            issues.append('A successful private Site deployment is required.')
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
        issues.append('Review destination evidence is missing or invalid.')
    return {'status': 'ready_for_human_review' if not issues else 'incomplete',
            'ready_for_human_review': not issues, 'url': record.get('url'), 'issues': issues,
            'quality_acceptance': 'defined_by_human_feedback'}
