cd /opt/teachbaseai

iframe_js=$(curl -fsS http://127.0.0.1:8080/iframe/ | sed -n "s/.*src=\"\(\/iframe\/assets\/.*\.js\)\".*/\1/p" | head -n 1)
main_js=$(curl -fsS http://127.0.0.1:8080/ | sed -n "s/.*src=\"\(\/assets\/.*\.js\)\".*/\1/p" | head -n 1)

echo "iframe_js=$iframe_js"
echo "main_js=$main_js"

if [ -n "$iframe_js" ]; then
  echo "--- iframe js mojibake scan ---"
  curl -fsS "http://127.0.0.1:8080$iframe_js" | grep -a -E "?|?|?|??" | head -n 3 || true
fi

if [ -n "$main_js" ]; then
  echo "--- main js mojibake scan ---"
  curl -fsS "http://127.0.0.1:8080$main_js" | grep -a -E "?|?|?|??" | head -n 3 || true
fi
