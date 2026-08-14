const http = require('http');
const server = http.createServer((req, res) => {
  const key = process.env.OPENAI_API_KEY || '';
  const prefix = key.substring(0, 6);
  res.writeHead(200, {'Content-Type': 'application/json'});
  res.end(JSON.stringify({status: 'ok', agent: 'openclaw', key_prefix: prefix, base_url: process.env.OPENAI_BASE_URL || ''}));
});
server.listen(8080, () => console.log('OpenClaw agent running on port 8080'));
