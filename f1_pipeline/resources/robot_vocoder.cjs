/* F1 adapter; the separately supplied Robot Voice Lab DSP retains its own license. */
'use strict';
const fs = require('node:fs');
const [modulePath, source, output, recipe] = process.argv.slice(2);
try {
  if (!modulePath || !source || !output || !recipe || fs.existsSync(output)) throw Error();
  const dsp = require(modulePath);
  const options = JSON.parse(recipe);
  const decoded = dsp.decodeWav(fs.readFileSync(source));
  if (decoded.sampleRate !== 48000 || decoded.samples.length > 48000 * 180) throw Error();
  // Match Voice Lab's worker normalization/resampling without importing its UI.
  const input = decoded.samples.slice();
  dsp.normalize(input, .8);
  const dry = dsp.resample(input, 48000, 22050);
  const wet = dsp.vocode(dry, 22050, options);
  const expected = dry.length + (options.echo > 0 ? Math.ceil(22050 * .6) : 0);
  if (wet.length !== expected || !wet.every(Number.isFinite)) throw Error();
  const restored = dsp.resample(wet, 22050, 48000);
  const samples = new Float32Array(decoded.samples.length + (options.echo > 0 ? 28800 : 0));
  samples.set(restored.subarray(0, samples.length));
  const temporary = output + '.processing';
  fs.writeFileSync(temporary, Buffer.from(dsp.encodeWav(samples, 48000)), {flag:'wx'});
  fs.renameSync(temporary, output);
} catch {
  process.stderr.write('Vocoder adapter failed.\n'); process.exitCode = 1;
}
