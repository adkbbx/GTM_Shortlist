// render.yaml uses JSON syntax, a YAML subset, to avoid adding a YAML dependency.
import { readFile } from 'node:fs/promises';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const response = await fetch('https://render.com/schema/render.yaml.json', { signal: AbortSignal.timeout(15000) });
if (!response.ok) throw new Error(`Render schema unavailable: HTTP ${response.status}`);
const schema = await response.json();
const blueprint = JSON.parse(await readFile(new URL('../render.yaml', import.meta.url), 'utf8'));
const validator = new Ajv2020({ strict: false, allErrors: true });
addFormats(validator);
const validate = validator.compile(schema);
if (!validate(blueprint)) {
  console.error(JSON.stringify(validate.errors, null, 2));
  process.exitCode = 1;
} else {
  console.log('Blueprint passes the published Render JSON Schema. No resources created or deployed.');
}
