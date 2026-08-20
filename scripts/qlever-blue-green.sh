#!/usr/bin/env bash
set -euo pipefail

action="${1:?action is required}"
slot="${2:?slot is required}"
snapshot="${3:-}"

case "$slot" in
  blue) port="${EQ_QLEVER_BLUE_PORT:-7011}" ;;
  green) port="${EQ_QLEVER_GREEN_PORT:-7012}" ;;
  *) echo "slot must be blue or green" >&2; exit 2 ;;
esac

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
qlever_root="${EQ_QLEVER_ROOT:-$repo_dir/var/qlever}"
slot_dir="$qlever_root/$slot"
template="${EQ_QLEVERFILE_TEMPLATE:-$repo_dir/ops/qlever/Qleverfile.template}"

case "$action" in
  prepare)
    [[ -d "$snapshot/nquads" ]] || { echo "missing snapshot nquads: $snapshot" >&2; exit 2; }
    mkdir -p "$slot_dir"
    if [[ -f "$slot_dir/Qleverfile" ]]; then
      (cd "$slot_dir" && qlever stop) || true
    fi
    ln -sfn "$snapshot/nquads" "$slot_dir/data"
    sed -e "s/@NAME@/earthquake-$slot/g" -e "s/@PORT@/$port/g" "$template" > "$slot_dir/Qleverfile.tmp"
    mv "$slot_dir/Qleverfile.tmp" "$slot_dir/Qleverfile"
    (cd "$slot_dir" && qlever index --overwrite-existing)
    ;;
  start)
    [[ -f "$slot_dir/Qleverfile" ]] || { echo "slot is not prepared: $slot_dir" >&2; exit 2; }
    (cd "$slot_dir" && qlever start)
    ;;
  activate)
    upstream_link="${EQ_NGINX_UPSTREAM_LINK:?EQ_NGINX_UPSTREAM_LINK is required}"
    upstream_dir="$(dirname "$upstream_link")"
    mkdir -p "$upstream_dir"
    upstream_tmp="$upstream_dir/.qlever-upstream-${slot}.tmp"
    printf 'server 127.0.0.1:%s;\n' "$port" > "$upstream_tmp"
    mv "$upstream_tmp" "$upstream_link"
    if [[ "${EQ_SKIP_NGINX_RELOAD:-0}" != "1" ]]; then
      sudo systemctl reload "${EQ_NGINX_SERVICE:-nginx}"
    fi
    ;;
  stop)
    [[ ! -f "$slot_dir/Qleverfile" ]] || (cd "$slot_dir" && qlever stop)
    ;;
  *)
    echo "usage: $0 {prepare|start|activate|stop} {blue|green} [snapshot]" >&2
    exit 2
    ;;
esac
