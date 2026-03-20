# 패키지 릴리스 런북

## 목적

이 저장소의 Python direct client, relay 패키지, Java 아티팩트를 릴리스 후보 수준으로 빌드하고 검증하는 절차를 정리합니다.

## 현재 범위

- Python 패키지 1: `clients/python`
- Python 패키지 2: `relay`
- Java 패키지: `clients/java`

> 이 저장소는 현재 GitHub Actions에서 **릴리스 아티팩트 빌드**까지 자동화합니다. 외부 레지스트리(PyPI, Maven Central) 실제 업로드는 별도 자격 증명이 필요하므로 이 런북은 credential-free 범위를 우선 다룹니다.

## 로컬 사전 검증

### Python client

```bash
cd clients/python
uv run pytest --cov=litellm_example --cov-fail-under=100 --cov-report=term-missing
uv run --with build python -m build
```

### relay

```bash
cd relay
uv run pytest --cov=litellm_relay --cov-fail-under=100 --cov-report=term-missing
uv run --with build python -m build
```

### Java

```bash
cd clients/java
mvn test
mvn -DskipTests package
```

## 산출물

### Python

- `clients/python/dist/*.whl`
- `clients/python/dist/*.tar.gz`
- `relay/dist/*.whl`
- `relay/dist/*.tar.gz`

### Java

- `clients/java/target/*.jar`

## GitHub Actions 워크플로우

- 파일: `.github/workflows/release-artifacts.yml`
- 트리거:
  - `push` on tags `v*`
  - `workflow_dispatch`

이 워크플로우는 다음을 수행합니다.

1. `clients/python` wheel/sdist 빌드
2. `relay` wheel/sdist 빌드
3. `clients/java` jar 빌드
4. 각 산출물을 GitHub Actions artifact로 업로드

## 권장 릴리스 순서

1. `main` 기준 CI green 확인
2. `mkdocs build --strict` 확인
3. Python 두 패키지와 Java 아티팩트 로컬 빌드
4. 필요하면 간단한 smoke install 수행
5. `vX.Y.Z` 태그 생성
6. `Release Artifacts` workflow 산출물 확인
7. 외부 레지스트리 업로드가 필요하면 별도 credential workflow에서 진행

## smoke install 예시

### Python client

```bash
cd clients/python
uv run --with build python -m build
python3 -m venv /tmp/litellm-python-smoke
source /tmp/litellm-python-smoke/bin/activate
pip install dist/*.whl
python -m litellm_example --help
deactivate
```

### relay

```bash
cd relay
uv run --with build python -m build
python3 -m venv /tmp/litellm-relay-smoke
source /tmp/litellm-relay-smoke/bin/activate
pip install dist/*.whl
litellm-relay --help
deactivate
```

### Java

```bash
cd clients/java
mvn -DskipTests package
java -cp target/litellm-o3-deep-research-java-0.1.0.jar example.litellm.Main --help
```

## 장애 시 점검 항목

- `pyproject.toml`의 `readme`/metadata 누락 여부
- `pom.xml`의 SCM/개발자 메타데이터 누락 여부
- `dist/` 또는 `target/` 산출물 생성 실패 여부
- tag push 없이 workflow를 기대하고 있지 않은지 여부
- 외부 패키지 레지스트리 자격 증명 부재 여부
