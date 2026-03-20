# GitHub Pages 배포 런북

## 목적

이 저장소의 한국어 문서를 GitHub Pages 형태로 배포하고, 배포 성공 여부를 점검하는 절차를 정리합니다.

## 배포 방식

- 소스: `docs/` + `mkdocs.yml`
- 빌드: MkDocs Material
- 배포: GitHub Actions `Deploy Docs` workflow (`.github/workflows/pages.yml`)가 `mkdocs build --strict`로 `site/`를 만든 뒤, GitHub Pages artifact 업로드 + `actions/deploy-pages`로 배포

## 기대 URL

- `https://seonghobae.github.io/litellm-o3-deep-research-rest-examples/`

## 배포 전 확인

```bash
python3 -m pip install -r requirements-docs.txt
mkdocs build --strict
```

또는 `Deploy Docs` workflow의 build job이 통과하는지 확인합니다.

현재 Pages 배포는 legacy `gh-pages` branch force-push 방식이 아니라 GitHub의 공식 artifact-based Pages deploy 경로를 사용합니다.

## 배포 후 확인

1. GitHub Actions `Deploy Docs` workflow 성공 여부 확인
2. GitHub Pages URL 접속 확인
3. 다음 핵심 문서 링크가 열리는지 확인
   - 홈
   - 시작하기
   - Python 직접 호출
   - Java 직접 호출
   - Relay 중계 예제

## 장애 시 점검 항목

- `mkdocs.yml` nav 경로 오타
- `requirements-docs.txt` 누락
- Pages workflow 권한 설정 오류
- GitHub Pages build source가 GitHub Actions로 인식되는지 여부
- `actions/configure-pages`, `actions/upload-pages-artifact`, `actions/deploy-pages` 버전 노후화 여부
- GitHub Actions annotation에 Pages 관련 런타임 경고가 다시 나타나는지 여부
