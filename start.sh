#!/usr/bin/env bash
set -euo pipefail

TOR_PID=""
BOT_PID=""
cleanup() {
  if [[ -n "${BOT_PID}" ]] && kill -0 "${BOT_PID}" 2>/dev/null; then
    kill "${BOT_PID}" 2>/dev/null || true
  fi
  if [[ -n "${TOR_PID}" ]] && kill -0 "${TOR_PID}" 2>/dev/null; then
    kill "${TOR_PID}" 2>/dev/null || true
  fi
  wait "${BOT_PID}" 2>/dev/null || true
  wait "${TOR_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [[ "${TOR_LOCAL_ENABLED:-false}" == "true" ]]; then
  TOR_SOCKS_PORT="${TOR_LOCAL_SOCKS_PORT:-9050}"
  TOR_DATA_DIR="${TOR_LOCAL_DATA_DIR:-/tmp/tor-data}"
  TOR_CONFIG="${TOR_LOCAL_CONFIG:-/tmp/torrc}"

  mkdir -p "${TOR_DATA_DIR}"
  TOR_USER_LINE=""
  if id debian-tor >/dev/null 2>&1; then
    chown -R debian-tor:debian-tor "${TOR_DATA_DIR}"
    TOR_USER_LINE="User debian-tor"
  fi

  cat > "${TOR_CONFIG}" <<EOF
ClientOnly 1
AvoidDiskWrites 1
DataDirectory ${TOR_DATA_DIR}
SocksPort 127.0.0.1:${TOR_SOCKS_PORT}
${TOR_USER_LINE}
Log notice stdout
EOF

  tor --verify-config -f "${TOR_CONFIG}"
  tor -f "${TOR_CONFIG}" &
  TOR_PID=$!

  ready=0
  for _ in $(seq 1 90); do
    if (echo >"/dev/tcp/127.0.0.1/${TOR_SOCKS_PORT}") >/dev/null 2>&1; then
      ready=1
      break
    fi
    if ! kill -0 "${TOR_PID}" 2>/dev/null; then
      echo "Tor exited before its SOCKS port became ready" >&2
      exit 1
    fi
    sleep 1
  done

  if [[ "${ready}" != "1" ]]; then
    echo "Tor SOCKS port did not become ready within 90 seconds" >&2
    exit 1
  fi

  export TOR_PROXY_SERVER="socks5://127.0.0.1:${TOR_SOCKS_PORT}"
  echo "Tor SOCKS proxy ready on loopback port ${TOR_SOCKS_PORT}"
fi

python bot.py &
BOT_PID=$!
if [[ -n "${TOR_PID}" ]]; then
  while kill -0 "${BOT_PID}" 2>/dev/null; do
    if ! kill -0 "${TOR_PID}" 2>/dev/null; then
      echo "Tor exited while GreyAI was running; stopping the bot for a clean restart" >&2
      kill "${BOT_PID}" 2>/dev/null || true
      wait "${BOT_PID}" 2>/dev/null || true
      exit 1
    fi
    sleep 2
  done
fi
wait "${BOT_PID}"
