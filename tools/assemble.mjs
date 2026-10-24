import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export const layers=[['base','style.css'],['workspace','workspaces.css'],['identity','identity.css'],['interface','interface.css'],['incumbent','legacy-workbench.css']];
export const cssExtras=['suite-controls.css','suite-cards.css','onboarding.css','desktop-ui.css','empty-workspaces.css','desktop-footer.css','public-appearance.css','settings-categories.css','updates.css','native-controls.css','tooltips.css'];
export const jsSources=['home-motion.js','feedback.js','suite-ui.js','suite-cards.js','onboarding.js','desktop-ui.js','settings-categories.js','updates.js','tooltips.js'];
export const app=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../static');
export async function expectedBundles(){
 const read=file=>fs.readFile(path.join(app,file),'utf8');
 let css='/* DAMN public interface. Rebuild with node tools/assemble.mjs. */\n@layer base,workspace,identity,interface,incumbent;\n';
 for(const [name,file] of layers)css+='@layer '+name+'{\n'+await read(file)+'\n}\n';
 const suite=await read('suite.css'),marker='/* Claude Opus 5.5: freely authored connected suite. */';
 const boundary=suite.indexOf(marker);if(boundary<0)throw Error('Missing authored suite boundary');
 css+=suite.slice(boundary);
 for(const file of cssExtras)css+='\n/* Source: '+file+' */\n'+await read(file);
 let js='/* DAMN public interface. Rebuild with node tools/assemble.mjs. */\n';
 for(const file of jsSources)js+='\n/* Source: '+file+' */\n'+await read(file)+'\n';
 return {'workbench.css':css,'motion.js':js};
}
export async function assemble({check=false}={}){const bundles=await expectedBundles();for(const [file,text] of Object.entries(bundles)){const output=path.join(app,file);if(check){if(await fs.readFile(output,'utf8')!==text)throw Error(file+' is stale; run node tools/assemble.mjs');}else await fs.writeFile(output,text,'utf8');}return Object.keys(bundles);}
if(typeof process!=='undefined'&&process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){await assemble({check:process.argv.includes('--check')});console.log(process.argv.includes('--check')?'Public bundles match their source files.':'Public interface bundles rebuilt.');}
