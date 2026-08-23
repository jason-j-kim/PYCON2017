#!/usr/bin/env bash
# 정책 아이디어 평가 — 리눅스 서버 설치
#
#   sudo bash deploy/setup_server.sh
#
# 하는 일은 여섯 가지다. 이미 되어 있는 것은 건너뛰므로 여러 번 돌려도 된다.
#   1) 전용 계정 policyeval 을 만든다 (root 로 돌리지 않기 위해)
#   2) /opt/policy-eval 에 코드를 놓고 파이썬 꾸러미를 깐다
#   3) mode.txt 를 정한다 (기본 personal — 방문자가 각자 키를 넣는다)
#   4) /etc/policy-eval.env 를 만들고 600 으로 잠근다
#   5) systemd 유닛을 걸고 켠다
#   6) 무엇이 남았는지 알려 준다 (nginx · 인증서는 손으로)
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/policy-eval}
ENV_FILE=/etc/policy-eval.env
SVC_USER=policyeval
SRC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

say() { printf '%s\n' "$*"; }
rule() { printf '%.0s-' {1..64}; echo; }

[ "$(id -u)" -eq 0 ] || { say "sudo 로 실행하세요."; exit 1; }

rule
say "  정책 아이디어 평가 — 서버 설치"
say "  코드: $SRC_DIR  →  $APP_DIR"
rule

# ── 1. 전용 계정 ──────────────────────────────────────────────────────
if id "$SVC_USER" >/dev/null 2>&1; then
  say "[1/6] 계정 $SVC_USER — 이미 있음"
else
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$SVC_USER"
  say "[1/6] 계정 $SVC_USER 만듦"
fi

# ── 2. 코드와 파이썬 꾸러미 ───────────────────────────────────────────
say "[2/6] 코드 배치와 파이썬 꾸러미"
if [ "$SRC_DIR" != "$APP_DIR" ]; then
  mkdir -p "$APP_DIR"
  # rsync 를 쓰지 않는다. 최소 설치 서버에는 없는 일이 흔하고, 이것 하나
  # 때문에 설치가 멈추면 곤란하다. tar 는 어디에나 있다.
  #
  # sessions.db(연구 자료)와 keys.local.bat 은 덮어쓰지 않는다 — 갱신할 때
  # 이미 쌓인 문답이 날아가면 되돌릴 수 없다. .venv 도 그대로 둔다.
  ( cd "$SRC_DIR" && tar cf - \
        --exclude='./.git' --exclude='__pycache__' --exclude='./.venv' \
        --exclude='./webapp/sessions.db' --exclude='./keys.local.bat' . ) \
    | ( cd "$APP_DIR" && tar xf - )
  say "      $SRC_DIR → $APP_DIR"
fi

command -v python3 >/dev/null || { say "  [!] python3 가 없습니다."; exit 1; }
PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
say "      파이썬 $PYV"
python3 - <<'PY' || { echo "  [!] 파이썬 3.10 이상이 필요합니다."; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY

[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/webapp/requirements.txt"
say "      fastapi · uvicorn 준비됨"

# ── 3. 판 정하기 ──────────────────────────────────────────────────────
# personal : 방문자가 각자 자기 API 키를 화면에 넣는다. 기관은 과금이 없다.
# experiment: 기관 키 하나로 전원이 쓴다. 밖에 열면 초대 코드가 새는 순간
#             남의 실험이 기관 카드로 결제된다. 외부 공개에는 권하지 않는다.
MODE=${MODE:-personal}
echo "$MODE" > "$APP_DIR/mode.txt"
say "[3/6] 판: $MODE"
if [ "$MODE" = "experiment" ]; then
  say "      [!] 기관 키 하나로 전원이 씁니다. 밖에 여신다면 콘솔에서"
  say "          그 키에 월 사용 한도를 반드시 걸어 두십시오."
fi

# ── 4. 환경 파일 ──────────────────────────────────────────────────────
if [ -f "$ENV_FILE" ]; then
  say "[4/6] $ENV_FILE — 이미 있음 (그대로 둡니다)"
else
  # 소문자·숫자 8자. base64 를 걸러 쓰면 버려지는 글자가 많아 길이가
  # 들쭉날쭉해진다(실제로 6자가 나왔다). 세 글자짜리 접속 코드는 없느니만
  # 못하므로 필요한 만큼 확실히 채운다.
  CODE=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 8) || true
  [ ${#CODE} -eq 8 ] || CODE="kdi$(date +%s | tail -c 6)"
  cat > "$ENV_FILE" <<EOF
# 정책 아이디어 평가 — 서버 설정
# 이 파일에 키가 들어갑니다. 권한 600 을 유지하십시오.

# 접속 코드 — 방문자가 평가를 시작할 때 넣는 값
SOCRATIC_ACCESS_CODE=$CODE

# 하루 세션 수 상한. 밖에 열어 두는 동안의 안전판입니다.
SOCRATIC_MAX_SESSIONS_PER_DAY=100

# 국회 의안 인증키 (선택) — open.assembly.go.kr 에서 발급
#ASSEMBLY_KEY=

# 기관 키로 운영할 때만(experiment 판) 채웁니다.
# personal 판에서는 비워 두십시오 — 채우면 방문자가 키를 안 넣어도
# 기관 키로 돌아가 과금이 이쪽에 붙습니다.
#ANTHROPIC_API_KEY=
EOF
  chmod 600 "$ENV_FILE"
  say "[4/6] $ENV_FILE 만듦 (600)"
  say "      접속 코드: $CODE   ← 방문자에게 알려 줄 값"
fi

chown -R "$SVC_USER:$SVC_USER" "$APP_DIR"

# ── 5. systemd ────────────────────────────────────────────────────────
install -m 644 "$APP_DIR/deploy/policy-eval.service" \
        /etc/systemd/system/policy-eval.service
systemctl daemon-reload
systemctl enable --now policy-eval
sleep 2
if systemctl is-active --quiet policy-eval; then
  say "[5/6] policy-eval 서비스 실행 중"
else
  say "[5/6] [!] 서비스가 뜨지 않았습니다:  journalctl -u policy-eval -n 50"
fi

# ── 6. 남은 것 ────────────────────────────────────────────────────────
rule
say "[6/6] 여기까지는 자동입니다. 남은 것은 손으로 하셔야 합니다."
say ""
say "  ① nginx 를 걸고 도메인을 정합니다"
say "       sudo cp $APP_DIR/deploy/nginx.conf \\"
say "               /etc/nginx/sites-available/policy-eval"
say "       (파일 안의 server_name 을 실제 도메인으로 바꿉니다)"
say "       sudo ln -s /etc/nginx/sites-available/policy-eval \\"
say "                  /etc/nginx/sites-enabled/"
say "       sudo nginx -t && sudo systemctl reload nginx"
say ""
say "  ② HTTPS 인증서를 받습니다 — 이건 선택이 아닙니다"
say "     (nginx.conf 에는 443 블록이 없습니다. certbot 이 붙여 줍니다.)"
say "       sudo certbot --nginx -d policy.example.ac.kr"
say "     방문자가 화면에 자기 API 키를 붙여넣습니다. 평문(http)으로"
say "     받으면 그 키가 도중에 드러납니다."
say ""
say "  ③ 기록은 SSH 터널로 봅니다 (밖에서는 404)"
say "       ssh -L 8000:127.0.0.1:8000 사용자@서버"
say "       브라우저에서 http://localhost:8000/records"
say ""
say "  ④ 문답 이력을 백업 대상에 넣습니다 — 이것이 연구 자료입니다"
say "       $APP_DIR/webapp/sessions.db"
rule
