# getogrand-hypermedia

[getogrand.media]의 소스 저장소.

## 의존성

이 소스를 로컬에서 개발하고 배포하기 위해서는 아래 의존성들을 미리 설치해야 합니다.

- [asdf-vm]: Node.js 런타임 관리를 위해 사용합니다. `aws-cdk`가 Node.js에 의존합니다.
- [aws-cli]: `aws-cdk`가 이에 의존합니다. 또한 ECR에 로그인하기 위해 필요합니다.
- [aws-cdk]: AWS에 인프라를 배포하기 위해 필요합니다.
- [Docker Engine]: 개발과 배포시에 Docker를 사용합니다.
    - macOS를 사용하는 경우 [Docker Desktop]을 통해 설치하기 보다는 [OrbStack] 이용을 추천합니다. [Docker Desktop]보다 메모리 회수가 훨씬 잘 됩니다.
- [Docker Compose]: 로컬에서 컨테이너들을 띄워 관리하기 위해 필요합니다.
- [uv]: Python 런타임 및 Virtual Environment, Python 의존성 패키지 등을 관리합니다.

### 선택 의존성

아래 의존성들은 필수는 아니지만 있으면 편리합니다.

- [ngrok]: 로컬에서 띄운 애플리케이션을 스마트폰으로 직접 보면서 스타일을 수정할 때 편리합니다.
- [autoenv]: 이 프로젝트 소스 디렉토리로 `cd` 했을 때 자동으로 `.env` 파일을 읽어 환경변수에 추가합니다.


[getogrand.media]: https://getogrand.media
[asdf-vm]: https://asdf-vm.com/
[uv]: https://github.com/astral-sh/uv
[aws-cli]: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html#getting-started-install-instructions
[aws-cdk]: https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html#getting_started_install
[Docker Engine]: https://docs.docker.com/engine/install/
[Docker Desktop]: https://docs.docker.com/desktop/install/mac-install/
[Docker Compose]: https://docs.docker.com/compose/install/
[OrbStack]: https://docs.orbstack.dev/install
[ngrok]: https://ngrok.com/docs/getting-started/
[autoenv]: https://github.com/hyperupcall/autoenv
