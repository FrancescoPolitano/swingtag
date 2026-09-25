// T-25: the CloudFront Function file can be unit-tested in Node without edits:
// load it into a vm context and call handler(). No exports needed in the file.
import { readFileSync } from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";
const ctx = {};
vm.runInNewContext(readFileSync(new URL("./rewrite.js", import.meta.url), "utf8"), ctx);
const cases = [
  ["/", "/index.html"],
  ["/3xk9m2p7qhv4", "/3xk9m2p7qhv4/index.html"],
  ["/3xk9m2p7qhv4/", "/3xk9m2p7qhv4/index.html"],
  ["/3xk9m2p7qhv4/care-sheet/care.pdf", "/3xk9m2p7qhv4/care-sheet/care.pdf"],
  ["/_assets/logo.svg", "/_assets/logo.svg"],
  ["/404.html", "/404.html"],
];
for (const [inp, out] of cases) {
  assert.equal(ctx.handler({ request: { uri: inp } }).uri, out, inp);
}
console.log(`PASS T-25: ${cases.length}/${cases.length} rewrite cases in node ${process.version}`);
