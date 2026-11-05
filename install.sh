#!/bin/sh
# Installs the nichiyou-daiku CLI: the prebuilt one for this system from a
# GitHub release, checked against the release's SHA256SUMS.
#
#   curl -fsSL https://raw.githubusercontent.com/ar90n/nichiyou-daiku/main/install.sh | sh
#   sh install.sh --version 0.2.0 --to ~/bin
#
# The plugin's entry point (bin/nichiyou-daiku) reads this file with
# NICHIYOU_DAIKU_LIBRARY set, for its functions only
set -eu

releases_page=https://github.com/ar90n/nichiyou-daiku/releases

# Sets system, machine, os, arch, exe, ext and target; os or arch stays
# empty where no prebuilt CLI is made
detect() {
  system=$(uname -s)
  machine=$(uname -m)
  exe=
  ext=tar.gz
  case $system in
    Linux) os=unknown-linux-musl ;;
    Darwin) os=apple-darwin ;;
    MINGW* | MSYS* | CYGWIN*) os=pc-windows-msvc exe=.exe ext=zip ;;
    *) os= ;;
  esac
  case $machine in
    x86_64 | amd64) arch=x86_64 ;;
    aarch64 | arm64) arch=aarch64 ;;
    *) arch= ;;
  esac
  target=$arch-$os
}

fetch() {
  if command -v curl >/dev/null 2>&1; then
    # Quiet: the reason we give says what failed
    curl -fsL -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2" "$1"
  else
    reason="neither curl nor wget is installed"
    return 1
  fi
}

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d ' ' -f 1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d ' ' -f 1
  else
    return 1
  fi
}

# Moves the CLI $1 into folder $2 whole: a run stopped halfway leaves none
place() {
  mkdir -p "$2" &&
    cp "$1" "$2/nichiyou-daiku$exe.part.$$" &&
    chmod +x "$2/nichiyou-daiku$exe.part.$$" &&
    mv -f "$2/nichiyou-daiku$exe.part.$$" "$2/nichiyou-daiku$exe"
}

# Puts version $1's CLI for this system in folder $2. On failure, $reason
# says why
download() {
  if [ -z "$os" ] || [ -z "$arch" ]; then
    reason="no prebuilt nichiyou-daiku for $system $machine"
    return 1
  fi
  work=$(mktemp -d) || { reason="cannot make a temporary folder"; return 1; }
  if unpack "$1" "$2"; then
    rm -rf "$work"
    return 0
  fi
  rm -rf "$work"
  return 1
}

unpack() {
  name=nichiyou-daiku-$1-$target.$ext
  base=${NICHIYOU_DAIKU_RELEASES:-$releases_page/download}/v$1
  reason="cannot fetch $base/$name"
  fetch "$base/$name" "$work/$name" || return 1
  reason="cannot fetch $base/SHA256SUMS"
  fetch "$base/SHA256SUMS" "$work/SHA256SUMS" || return 1
  want=$(awk -v n="$name" '$2 == n || $2 == "*" n { print $1 }' "$work/SHA256SUMS")
  if ! got=$(sha256 "$work/$name"); then
    reason="neither sha256sum nor shasum is installed to check it"
    return 1
  fi
  if [ -z "$want" ] || [ "$want" != "$got" ]; then
    reason="its checksum does not match SHA256SUMS"
    return 1
  fi
  mkdir "$work/out"
  # set -e does not reach into a function called as an if's condition
  case $ext in
    zip) unzip -q "$work/$name" -d "$work/out" ;;
    *) tar -xzf "$work/$name" -C "$work/out" ;;
  esac || { reason="cannot unpack $name"; return 1; }
  place "$work/out/nichiyou-daiku$exe" "$2" || { reason="cannot put it in $2"; return 1; }
}

# Sets version to the newest release's: the tag GitHub's /releases/latest
# moves to (its API would be limited to 60 calls an hour). On failure,
# $reason says why
latest() {
  url=${NICHIYOU_DAIKU_LATEST:-$releases_page/latest}
  reason="cannot reach $url"
  if command -v curl >/dev/null 2>&1; then
    final=$(curl -fsSL -o /dev/null -w '%{url_effective}' "$url") || return 1
  elif command -v wget >/dev/null 2>&1; then
    # -S shows each redirect's Location; -q would hide it too
    final=$(wget -S -O /dev/null "$url" 2>&1 | sed -n 's/^ *Location: *\([^ ]*\).*/\1/p' | tail -n 1)
  else
    reason="neither curl nor wget is installed"
    return 1
  fi
  case $final in
    */tag/v?*) version=${final##*/tag/v} ;;
    *)
      reason="$url leads to no release"
      return 1
      ;;
  esac
}

fail() {
  printf 'nichiyou-daiku: %s\n' "$1" >&2
  exit 1
}

# Says what would keep the new CLI from running: its folder off PATH, or an
# older nichiyou-daiku (the Python version, which has no --version) on PATH
advise() {
  case :$PATH: in
    *":$1:"*) ;;
    *) printf 'nichiyou-daiku: %s is not on PATH; add it, e.g. with export PATH="%s:$PATH" in your shell profile\n' "$1" "$1" >&2 ;;
  esac
  set -f
  saved_ifs=$IFS
  IFS=:
  for dir in $PATH; do
    if [ -n "$dir" ] && [ "$dir" != "$1" ] && [ -x "$dir/nichiyou-daiku" ] &&
      ! "$dir/nichiyou-daiku" --version >/dev/null 2>&1; then
      printf 'nichiyou-daiku: %s is an older nichiyou-daiku (the Python version); remove it with: uv tool uninstall nichiyou-daiku\n' "$dir/nichiyou-daiku" >&2
      break
    fi
  done
  IFS=$saved_ifs
  set +f
}

main() {
  version=${NICHIYOU_DAIKU_VERSION:-}
  to=${NICHIYOU_DAIKU_INSTALL_DIR:-$HOME/.local/bin}
  while [ $# -gt 0 ]; do
    case $1 in
      --version | --to)
        [ $# -ge 2 ] || fail "$1 needs a value: install.sh [--version VERSION] [--to FOLDER]"
        case $1 in --version) version=$2 ;; *) to=$2 ;; esac
        shift 2
        ;;
      *) fail "unknown option $1: install.sh [--version VERSION] [--to FOLDER]" ;;
    esac
  done
  version=${version#v}
  reason=
  detect
  if [ -z "$os" ] || [ -z "$arch" ]; then
    fail "no prebuilt nichiyou-daiku for $system $machine; build it from source as the README says"
  fi
  if [ -z "$version" ]; then
    latest || fail "cannot find the newest release ($reason); name one with --version, see $releases_page"
  fi
  # uv tool install puts the Python version here too, and uv tool uninstall
  # would later remove whatever stands in its place
  old=$to/nichiyou-daiku$exe
  if [ -f "$old" ] && [ -x "$old" ] && ! "$old" --version >/dev/null 2>&1; then
    fail "$old does not answer --version: it is the Python version (remove it with: uv tool uninstall nichiyou-daiku) or a broken copy (delete it); then run this again"
  fi
  download "$version" "$to" || fail "could not install v$version ($reason); see $releases_page"
  printf 'nichiyou-daiku: installed v%s for %s in %s\n' "$version" "$target" "$to" >&2
  advise "$to"
}

if [ -z "${NICHIYOU_DAIKU_LIBRARY:-}" ]; then
  main "$@"
fi
