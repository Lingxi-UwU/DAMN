import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const tests=(await fs.readdir(root)).filter(name=>/^test_.*\.cjs$/.test(name)).sort();
for(const test of tests){const result=spawnSync(process.execPath,[test],{cwd:root,stdio:'inherit',windowsHide:true});if(result.error)throw result.error;if(result.status!==0)process.exit(result.status||1);}
console.log('Passed '+tests.length+' frontend suites.');
