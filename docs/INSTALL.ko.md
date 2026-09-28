# 설치 매뉴얼 (한국어)

## 1. 준비 사항

Windows 10/11에 Python 3.11 이상과 Codex Desktop을 설치합니다. Codex에
로그인하고 Gmail을 연결합니다. 예약 시간에는 PC가 켜져 있고 해당 Windows
사용자가 로그인되어 있어야 합니다.

## 2. 자동 설치

저장소 폴더에서 PowerShell을 열고 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

설치기는 `.venv` 생성, 패키지 설치, 누락된 예제 설정 복사,
`PaperNewsletterCollect` 작업 등록, 상태 진단을 수행합니다. 기존 설정과
처리 완료 state는 덮어쓰지 않습니다.

최초 설치 후 다음 파일을 수정합니다.

- `config/settings.toml`: 수신자, 시간대, Crossref 연락처, 공개 저장소 주소
- `config/feeds.opml`: Feedly 등에서 내보낸 OPML
- `config/profile.md`: 연구 관심사, 포함 기준, 제외 기준
- `config/my_papers.bib`: Zotero Better BibTeX export

`paper-newsletter doctor`를 실행하여 실패 항목이 없어질 때까지 설정합니다.
[사용자 설정 가이드](CONFIGURATION.ko.md)에서 각 항목과 파일의 입력법을 확인할 수 있습니다.

## 3. 수동 설치

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item config\settings.example.toml config\settings.toml
Copy-Item config\feeds.example.opml config\feeds.opml
Copy-Item config\profile.example.md config\profile.md
Copy-Item config\my_papers.example.bib config\my_papers.bib
.\.venv\Scripts\paper-newsletter.exe doctor
```

Windows 작업 스케줄러에서 `scripts/collect_daily.ps1`을 매일 실행하도록
등록합니다. 프로그램은 `powershell.exe`, 인수는 다음 형식입니다.

```text
-NoProfile -ExecutionPolicy Bypass -File "<프로젝트>\scripts\collect_daily.ps1"
```

**사용자가 로그온할 때만 실행**을 선택합니다. 기본 수집 시간은
`config/settings.toml`의 09:40입니다.

## 4. Codex와 Gmail 연결

Codex에서 Gmail을 연결합니다. 이 저장소를 workspace로 사용하는 매일 10:00
자동화를 만들고 `automation/daily-paper-digest.prompt.md` 내용을 prompt로
사용합니다. 20분 간격은 RSS 재시도가 끝날 시간을 확보하기 위한 것입니다.

`paper-newsletter collect`로 수집을 시험한 뒤 Codex에서 현재 후보의 scoring과
렌더링을 시험합니다. 테스트 발송에서는 `--no-mark-processed`를 유지하고,
실제 Gmail 발송 성공을 확인한 뒤에만 `paper-newsletter mark-processed`를
실행합니다.

## 5. 백업, 복원, 제거

```powershell
paper-newsletter backup
paper-newsletter restore --backup-file backups\paper-newsletter-backup-YYYYMMDD-HHMMSS.zip --yes
powershell -ExecutionPolicy Bypass -File scripts/uninstall.ps1
```

제거 스크립트는 개인 설정, state, 결과물, 로그, 백업을 보존합니다.
