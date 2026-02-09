#!/bin/sh
set -e
curl -fsS http://127.0.0.1:8080/api/v1/bitrix/health || true
