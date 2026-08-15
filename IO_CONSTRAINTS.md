# ⚠️ 紧急约束(指挥者 2026-08-15 18:12)

你的全目录 grep(-rlE /app/.next/server/chunks 5000+ 文件)打爆了 120 磁盘 IO(load 18,97% wa),
导致 hermes 容器 node 写日志卡死。已强制 kill。

**从现在起禁止:**
- ❌ 禁止 `grep -rlE pattern /app/.next/server/chunks`(全目录递归扫描)
- ❌ 禁止 `grep -r pattern /app/.next`(大目录)

**允许:**
- ✅ `ls /app/.next/server/chunks | wc -l`(看规模)
- ✅ 用 `grep -l pattern /app/.next/server/chunks/<已知文件>.js`(单文件或 ≤10 个已知文件)
- ✅ 用 find + head 限量: `find /app/.next/server/chunks -name '*.js' | head -20 | xargs grep -l pattern`
- ✅ 读已知路由文件(如 route.js)用 read/cat
- ✅ node -e 脚本内 fs.readFileSync 精确文件

**原则:每次 grep 的文件数 ≤ 10 个,或先 find 限量再 grep。**
