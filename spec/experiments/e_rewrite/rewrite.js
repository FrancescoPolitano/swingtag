// Candidate rewrite function (ES5), as in SPEC 10.7.
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri === '/' || uri === '') { request.uri = '/index.html'; return request; }
  if (uri.charAt(uri.length - 1) === '/') { request.uri = uri + 'index.html'; return request; }
  var lastSegment = uri.substring(uri.lastIndexOf('/') + 1);
  if (lastSegment.indexOf('.') === -1) { request.uri = uri + '/index.html'; }
  return request;
}
