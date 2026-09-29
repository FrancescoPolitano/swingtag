// Unit test of the CloudFront Function: the file is loaded as is
// into a vm context and handler() is called. Run: node terraform/functions/test_rewrite.mjs
import { readFileSync } from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";

const context = {};
vm.runInNewContext(readFileSync(new URL("./rewrite.js", import.meta.url), "utf8"), context);
const cases = [
  ["JS-01 root", "/", "/index.html"],
  ["JS-02 token", "/3xk9m2p7qhv4", "/3xk9m2p7qhv4/index.html"],
  ["JS-03 token_slash", "/3xk9m2p7qhv4/", "/3xk9m2p7qhv4/index.html"],
  ["JS-04 resource", "/3xk9m2p7qhv4/care-sheet/care.pdf", "/3xk9m2p7qhv4/care-sheet/care.pdf"],
  ["JS-05 assets", "/_assets/logo.svg", "/_assets/logo.svg"],
  ["JS-06 error_page", "/404.html", "/404.html"],
];
for (const [name, input, expected] of cases) {
  assert.equal(context.handler({ request: { uri: input } }).uri, expected, name);
}
console.log(`${cases.length}/${cases.length} rewrite cases passed`);
