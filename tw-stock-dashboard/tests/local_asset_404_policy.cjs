'use strict';
// The frozen premarket reference is optional until its first successful 08:27-08:57 run.
// A missing optional snapshot must not hide broken assets or failed snapshot delivery.
const path=require('node:path');
const OPTIONAL='data/market_premarket/latest.json';
function classifyLocalAssetError(error,root,existsSync){
  if(error?.url===OPTIONAL&&error?.code===404&&!existsSync(path.join(root,OPTIONAL)))
    return 'optional-unpublished-premarket';
  return 'unexpected';
}
module.exports={classifyLocalAssetError};
