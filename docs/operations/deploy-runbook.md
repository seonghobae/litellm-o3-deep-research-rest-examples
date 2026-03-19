# GitHub Pages 배포 런북

## 목적

이 저장소의 한국어 문서를 GitHub Pages 형태로 배포하고, 배포 성공 여부를 점검하는 절차를 정리합니다.

## 배포 방식

- 소스: `docs/` + `mkdocs.yml`
- 빌드: MkDocs Material
- 배포: GitHub Actions `pages.yml`

## 기대 URL

- `https://seonghobae.github.io/litellm-o3-deep-research-rest-examples/`

## 배포 전 확인

```bash
python3 -m pip install -r requirements-docs.txt
mkdocs build --strict
```

또는 CI에서 docs job이 통과하는지 확인합니다.

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
