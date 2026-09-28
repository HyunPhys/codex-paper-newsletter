# 사용자 설정 가이드

이 문서는 설치 후 `config/` 폴더에 무엇을 넣어야 하는지 설명합니다. 설정 파일에는
Gmail 비밀번호나 API 키를 넣지 않습니다. Gmail 인증은 Codex 연결에서 관리합니다.

## 설정 순서

1. `settings.example.toml`을 `settings.toml`로 복사합니다.
2. `feeds.example.opml`을 `feeds.opml`로 복사하거나 Feedly OPML로 교체합니다.
3. `profile.example.md`를 `profile.md`로 복사하고 연구 기준을 작성합니다.
4. Zotero 문헌을 `my_papers.bib`로 export합니다.
5. `paper-newsletter doctor`로 설정을 검사합니다.
6. 수동 수집 후 Codex 자동화와 Gmail 발송을 시험합니다.

자동 설치 스크립트는 1~3단계의 파일이 없을 때만 예제 파일을 복사합니다. 기존
개인 설정은 덮어쓰지 않습니다.

## `settings.toml`

프로그램 전체의 경로, 메일, scoring, 수집, 네트워크 설정입니다.

### `[paths]`

| 항목 | 의미 | 기본값 |
| --- | --- | --- |
| `feeds_opml` | 수집할 RSS 목록 | `config/feeds.opml` |
| `profile_md` | 명시적인 연구 관심사와 제외 기준 | `config/profile.md` |
| `my_papers_md` | 선택 사항인 수동 추천 문헌 메모 | `config/my_papers.md` |
| `my_papers_bib` | Zotero BibTeX export | `config/my_papers.bib` |
| `email_template` | 로컬 Markdown digest 템플릿 | `config/email_template.md` |
| `state_file` | 이미 처리한 논문 key 목록 | `state/processed.json` |
| `out_dir` | candidates, scores, 메일 payload 출력 폴더 | `out` |

일반적인 설치에서는 이 경로들을 바꿀 필요가 없습니다. 상대 경로는 프로젝트
루트를 기준으로 해석됩니다.

### `[newsletter]`

```toml
[newsletter]
email_to = "your-address@example.com"
timezone = "Asia/Seoul"
threshold = 3.0
top_n = 5
developer_name = "Byunghyun Kim"
developer_email = "bhkim133@gmail.com"
project_url = "https://github.com/HyunPhys/codex-paper-newsletter"
```

- `email_to`: 실제 뉴스레터 수신 주소입니다. Gmail 로그인 주소와 달라도 됩니다.
- `timezone`: 논문 날짜 경계와 candidates 최신성 판단에 사용합니다.
- `threshold`: 이 점수 이상인 논문이 relevant paper 표에 들어갑니다.
- `top_n`: 자세한 요약과 초록을 표시할 상위 논문 수입니다.
- `developer_*`, `project_url`: 메일 맨 아래의 개발자 footer에 사용합니다.

점수는 `0.0, 0.5, ... 5.0`의 반 점수 단위입니다. threshold를 너무 낮추면
메일이 길어지고, 너무 높이면 broad field picks만 남을 수 있습니다.

### `[collection]`, `[digest]`, `[network]`

- `schedule_time`: 각각 Windows RSS 수집과 Codex digest의 권장 실행 시간입니다.
  설치기는 `collection.schedule_time`으로 작업 스케줄러를 등록합니다. Codex
  자동화 시간은 Codex 화면에서 직접 맞춰야 합니다.
- `attempts`, `retry_delay_seconds`: 일시적인 feed 장애 재시도 횟수와 간격입니다.
- `dated_feed_lookback_days`: 일반 저널 feed의 날짜 여유 구간입니다.
- `arxiv_lookback_days`: arXiv feed의 별도 날짜 여유 구간입니다.
- `crossref_email`: DOI 보강 요청의 정중한 연락처입니다. Crossref 비밀번호나
  계정 인증값이 아닙니다.
- timeout, retries, response size는 느리거나 비정상적으로 큰 응답을 제한합니다.

## `feeds.opml`: RSS와 저널 목록

이 파일은 Feedly 등의 **OPML export**입니다. 각 feed의 `xmlUrl`이 실제 RSS,
Atom 또는 RDF 주소이고, `title` 또는 `text`가 뉴스레터의 저널명으로 표시됩니다.

```xml
<outline type="rss"
         title="Nature Materials"
         text="Nature Materials"
         xmlUrl="https://www.nature.com/nmat.rss" />
```

- Feedly에서 OPML을 export한 뒤 파일명을 `feeds.opml`로 바꾸면 됩니다.
- 직접 편집할 때는 URL 안의 `&`를 `&amp;`로 XML escape합니다.
- 같은 `xmlUrl`은 한 번만 수집됩니다.
- feed가 하루 동안 0편을 내는 것은 정상이며, 최종 저널 표에 0으로 표시됩니다.
- 논문 웹페이지 URL이 아니라 RSS/Atom feed URL을 넣어야 합니다.
- 일부 publisher feed는 날짜나 초록을 불완전하게 제공하므로 코드가 논문 페이지
  metadata를 추가로 읽을 수 있습니다.

추가 후 `paper-newsletter collect --collection-attempts 1
--collection-retry-delay-seconds 0`으로 짧게 시험하고 `feed_errors`를 확인합니다.

## `profile.md`: 직접적인 scoring 기준

이 파일은 가장 안정적이고 우선순위가 높은 연구 기준입니다. 자유로운 설명을
쓸 수 있지만 로컬 fallback scorer를 위해 다음 영문 heading은 유지합니다.

```markdown
# Research Profile

## Research interests
Twisted two-dimensional materials, reconstructed domains, and TEM.

## Include Keywords
- moire reconstruction
- domain wall
- 4D-STEM

## Exclude Keywords
- battery-only
- correction

## Scoring guidance
5.0 means a direct match to the current research program.
```

재료 이름만 나열하기보다 관심 있는 **재료, 구조, 메커니즘, 측정법, 연구 질문**을
함께 적는 것이 좋습니다. 제외 기준에는 실제로 낮게 평가하고 싶은 이유를 씁니다.
어떤 논문이 반복해서 잘못 분류되면 문헌 하나를 강제로 override하기보다 그 판단
규칙을 profile에 추가합니다.

## `my_papers.bib`: Zotero 기반 연구 문맥

Zotero에서 자신의 논문과 핵심 참고문헌 collection을 선택하고 Better BibTeX
형식으로 export하여 `config/my_papers.bib`로 저장합니다. UTF-8 텍스트여야 하며
최소한 `title`이 필요합니다. `year`, `journal` 또는 `booktitle`, `keywords`가
있으면 문맥 품질이 좋아집니다.

```bibtex
@article{researcher2026,
  title = {Domain reconstruction in twisted layered materials},
  author = {Researcher, Example},
  journal = {Example Journal},
  year = {2026},
  keywords = {moire, domain wall, electron microscopy}
}
```

코드는 전체 library를 고르게 대표하기 위해 제목, 연도, 저널, keyword를 압축해
Codex에 전달합니다. 긴 abstract는 일부 앞쪽 문헌이 context를 독점하지 않도록
의도적으로 제외합니다. BibTeX는 **positive example library**이고 `profile.md`의
명시적 제외 규칙이나 점수 체계를 자동으로 덮어쓰지 않습니다.

Zotero 목록을 갱신할 때 같은 경로의 파일을 새 export로 교체하면 다음 수집부터
반영됩니다. 개인 library이므로 공개 저장소에는 commit하지 마십시오.

## `my_papers.md`와 `email_template.md`

- `my_papers.md`는 BibTeX 외에 반드시 강조할 문헌이나 연구 방향을 자유롭게 적는
  선택 파일입니다. 없어도 됩니다.
- `email_template.md`는 보관용 `digest-YYYY-MM-DD.md`의 섹션과 placeholder를
  제어합니다. Gmail용 HTML과 평문은 메일 클라이언트 호환성을 위해 Python
  renderer가 별도로 만듭니다. 템플릿만 바꿔 Gmail 디자인이 모두 바뀌지는 않습니다.

## Gmail과 Codex 자동화

1. Codex에서 Gmail 연결을 승인합니다. 비밀번호를 설정 파일에 쓰지 않습니다.
2. `automation/daily-paper-digest.prompt.md`로 매일 자동화를 만듭니다.
3. 자동화는 `latest_email.json`의 `to`, `subject`, `body`, `body_html`을 사용합니다.
4. Gmail send 성공 후에만 `mark-processed`를 실행합니다.

메일 주소를 바꾸려면 `settings.toml`의 `email_to`만 바꾸고 `doctor`를 실행합니다.
Gmail 연결이 끊겼다면 state를 먼저 갱신하지 말고 재연결 후 기존 payload를 다시
보냅니다.

## 개인정보와 검증

공개 Git에 올리면 안 되는 파일은 `settings.toml`, `profile.md`, `my_papers.bib`,
`state/`, `out/`, `logs/`, `backups/`입니다. 공개 저장소의 `.gitignore`가 이를
제외하지만 commit 전에 항상 `git status`를 확인합니다.

```powershell
paper-newsletter doctor
paper-newsletter backup
python -m pytest
```

`doctor`가 실패하면 예약 발송을 켜기 전에 해당 설정을 수정합니다.
