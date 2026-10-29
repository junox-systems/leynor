# Changelog

## [0.6.0](https://github.com/junox-systems/django-starter-kit/compare/v0.5.0...v0.6.0) (2026-10-29)


### ⚠ BREAKING CHANGES

* **email:** POSTMARK_SERVER_TOKEN is ignored. Set RESEND_API_KEY or EMAIL_URL before deploying.

### Features

* **email:** Resend or any SMTP server, drop Postmark ([a55e975](https://github.com/junox-systems/django-starter-kit/commit/a55e97588eaa2089c2d83050b5f2069ac9b297ce))
* **storage:** choose media backend with STORAGE_BACKEND ([7e18141](https://github.com/junox-systems/django-starter-kit/commit/7e181416febac3d7a6c5a5f3869670f714308e68))


### Bug Fixes

* **ci:** unblock deploy check on a clean checkout ([c2480f7](https://github.com/junox-systems/django-starter-kit/commit/c2480f779d94d3a21246479f582e6f5ffdab5990))
* **dev:** keep just dev inside Docker and stop it failing silently ([f22918a](https://github.com/junox-systems/django-starter-kit/commit/f22918a34d8384c1ad5999132ab9b553f1428962))

## [0.5.0](https://github.com/junox-systems/django-starter-kit/compare/v0.4.0...v0.5.0) (2026-10-22)


### Features

* **messages:** show Django messages as Basecoat toasts ([864037a](https://github.com/junox-systems/django-starter-kit/commit/864037a4167c4fc32edc6cfed8e299719aaf42fc))
* **orgs:** toast on org switch ([ee29936](https://github.com/junox-systems/django-starter-kit/commit/ee299365b251e6b0ba66f8f406f889c6db2ebe17))
* **sidebar:** collapse to icon rail on desktop ([3c0a7c5](https://github.com/junox-systems/django-starter-kit/commit/3c0a7c5180b32ee1b7add8119be4740dc60fd994))
* **users:** add editable profile and avatar ([7cb2c31](https://github.com/junox-systems/django-starter-kit/commit/7cb2c317cc2e5e1f2934006c3e1229afa436017b))
* **users:** avatar field with live preview ([3c6d8cf](https://github.com/junox-systems/django-starter-kit/commit/3c6d8cfcab9312b7540af0a7236adb4104312be2))


### Bug Fixes

* **build:** pin python 3.14.8 in mise configs ([4d602f5](https://github.com/junox-systems/django-starter-kit/commit/4d602f58b91921f9235fe89a1f2473a1cfa87c04))
* **header:** drop admin link, single auth CTA ([4ce173b](https://github.com/junox-systems/django-starter-kit/commit/4ce173ba7347bc97d62bf72210917dac3adb0da2))
* **orgs:** move org switcher to dashboard as auto-submit select ([b195592](https://github.com/junox-systems/django-starter-kit/commit/b195592b63ca501c087d59835ee1a715e0f156d4))
* **sidebar:** align logout icon with label ([0956fb9](https://github.com/junox-systems/django-starter-kit/commit/0956fb9769802e57eef584a3030cc95c2def865e))
* **sidebar:** distinct, destructive logout ([7bfde3f](https://github.com/junox-systems/django-starter-kit/commit/7bfde3f60b189973f2d13d8283258cbf8d4a7708))
* **toast:** top-right below nav, calmer entrance ([82b6ef5](https://github.com/junox-systems/django-starter-kit/commit/82b6ef577abf7c580c9eb0a688208e4bee587802))
* **users:** apply allauth username rules on profile edit ([00d71e2](https://github.com/junox-systems/django-starter-kit/commit/00d71e2bb7963954a57ee592d9020e94485f738d))
* **users:** enforce case-insensitive unique username in DB ([141ed2a](https://github.com/junox-systems/django-starter-kit/commit/141ed2af12469560d80029941dc6b70a94b633b5))
* **users:** harden avatar upload and profile save ([72e6b40](https://github.com/junox-systems/django-starter-kit/commit/72e6b4056e5561af536c75fc68d933e9d0df02a3))
* **users:** profile logout + long name wrap ([ed8f1c8](https://github.com/junox-systems/django-starter-kit/commit/ed8f1c89b3f679527a7a9838ebc0a14605ad8bb5))

## [0.4.0](https://github.com/junox-systems/django-starter-kit/compare/v0.3.0...v0.4.0) (2026-10-21)


### ⚠ BREAKING CHANGES

* **orgs:** Membership.role is replaced by Membership.roles. Migration orgs 0002 converts owner/member values and gives users without an org a personal one; reversing it maps admin to member.

### Features

* **orgs:** add INCITS 359 RBAC, personal orgs, org switcher ([d5ee9ca](https://github.com/junox-systems/django-starter-kit/commit/d5ee9cae2321aad589f214be8d6da7d0530c3c00))
* **templates:** build server markup from cotton components ([ed43e6f](https://github.com/junox-systems/django-starter-kit/commit/ed43e6f248f707bc338541ee37dc6d5b67517f74))


### Bug Fixes

* **orgs:** close RBAC review gaps ([726ad73](https://github.com/junox-systems/django-starter-kit/commit/726ad738cf0307ba68091eaf2941673685dc0ea6))

## [0.3.0](https://github.com/junox-systems/django-starter-kit/compare/v0.2.0...v0.3.0) (2026-10-20)


### ⚠ BREAKING CHANGES

* **docker:** apt replaces dnf in both images; extend them with Debian package names.
* REDIS_URL and the cache/redis services are gone. Constance values previously stored in Redis are not migrated; re-enter them in the admin.
* **tasks:** worker and beat services/recipes become qcluster. Periodic tasks must be recreated as django_q Schedules. Old django_celery_* tables are left in place, not dropped.
* **stack:** web no longer publishes 8000; traffic enters on 80/443 via nginx. NGINX_CERTS_DIR (fullchain.pem + privkey.pem) is required to deploy.
* **frontend:** data-turbo / data-turbo-permanent are gone; use hx-boost="false" / hx-preserve.

### Features

* add AWS_S3_ENDPOINT_URL for S3-compatible storage backends ([a8b8a87](https://github.com/junox-systems/django-starter-kit/commit/a8b8a874f2b5eae3a58022fb7bc0f4cd3262e0a1))
* add clickstack observability to dev compose with analytics profile ([341ac64](https://github.com/junox-systems/django-starter-kit/commit/341ac64c01b3fc29a0f0b942ebc1f1b04144a17a))
* add docker swarm stack file replacing root compose ([678ffce](https://github.com/junox-systems/django-starter-kit/commit/678ffce470c0706b4e5c1e515bc55008325467a6))
* add generic Stimulus controller for Svelte mounting ([e3a41f2](https://github.com/junox-systems/django-starter-kit/commit/e3a41f2d01d750e50e9381baa679b90bf696e8e8))
* add prod entrypoint script with db wait + migrate ([835c71b](https://github.com/junox-systems/django-starter-kit/commit/835c71b8d5fcaa724beebff47d7b87335df7863a))
* add rustfs S3 service to dev compose ([b4bfd9b](https://github.com/junox-systems/django-starter-kit/commit/b4bfd9bcf4bcc348e47b242f118bc6844aa4b298))
* add swarm stack targets and analytics profile shortcut to Makefile ([22674f7](https://github.com/junox-systems/django-starter-kit/commit/22674f75177ac56554c2cb6d02ec77c49e15ad64))
* **auth:** enable allauth MFA (TOTP + recovery codes) ([25c4d57](https://github.com/junox-systems/django-starter-kit/commit/25c4d57fc794cd052654c0cfcbc9bbe3bcd4f52c))
* configurable otel log level per environment ([a07ef3d](https://github.com/junox-systems/django-starter-kit/commit/a07ef3d76615e18cd1a4cb3d5a27187fafc0f9ea))
* **core:** add /healthz/ with DB ping ([e9efd84](https://github.com/junox-systems/django-starter-kit/commit/e9efd84f6ba36149b8e088c37fe3a29a7182d7fd))
* **dashboard:** authenticated app shell with Turbo + Svelte sidebar ([96633fd](https://github.com/junox-systems/django-starter-kit/commit/96633fd3586c5589d75c0239f2e134197e7c7998))
* **dashboard:** move activity to own page under account ([d11c916](https://github.com/junox-systems/django-starter-kit/commit/d11c9164e38382e2fd1f2b358747d41073c6d155))
* **db:** switch Postgres to ParadeDB 0.26.2 on PG18 ([d578dee](https://github.com/junox-systems/django-starter-kit/commit/d578deef5edb8bbe432e51cc893d0bf074fe07f4))
* **dev:** print service URLs after dev and dev-slim ([00628a1](https://github.com/junox-systems/django-starter-kit/commit/00628a18aeeb258a527e84ccca7f3d7ca544d7d8))
* **dev:** run celery beat, make analytics default ([40bd28e](https://github.com/junox-systems/django-starter-kit/commit/40bd28eda3538175ea2c826c0bfb679b905752ec))
* **email:** send HTML alongside plain text ([d76ca4b](https://github.com/junox-systems/django-starter-kit/commit/d76ca4b17972fa1719dc8537ec35b934892cc61a))
* **frontend:** replace turbo drive with htmx 4 ([c68b76b](https://github.com/junox-systems/django-starter-kit/commit/c68b76b587992fbda5369371aabac517fdcd51c1))
* **orgs:** add organizations with members and invites ([d4842c6](https://github.com/junox-systems/django-starter-kit/commit/d4842c678a91f4e11dcd6ec37c9de8becdf5b434))
* **orgs:** expire invitations after 7 days ([af3d4bf](https://github.com/junox-systems/django-starter-kit/commit/af3d4bfde0ce88819258acc4e369072e156a8619))
* **orgs:** let owners change member roles ([777e741](https://github.com/junox-systems/django-starter-kit/commit/777e74110be2b88dec7df5a543284145a88fb65d))
* **pages:** add terms and privacy placeholder pages ([e6fe8b8](https://github.com/junox-systems/django-starter-kit/commit/e6fe8b8e0c6d638e895e0b2e862f2234af1832b1))
* **pages:** serve robots.txt and sitemap.xml ([9ee9a7b](https://github.com/junox-systems/django-starter-kit/commit/9ee9a7b9e27aaba73eb640d1c9d30e228cdd8384))
* particle-logo hero with official Svelte mark ([05f3dc5](https://github.com/junox-systems/django-starter-kit/commit/05f3dc5c47b1643a3f9ec5f24dc439c6df32cbdd))
* remove htmx — Django forms + Stimulus + Svelte islands replace it ([7564c2e](https://github.com/junox-systems/django-starter-kit/commit/7564c2efaa83cd3f576b322f3bec12fa6baf5f06))
* render account management pages inside the app shell ([d5b34b1](https://github.com/junox-systems/django-starter-kit/commit/d5b34b1b09436d55f5839903aaadfb4ac20bbe57))
* render social account connections inside the app shell ([bbb5d71](https://github.com/junox-systems/django-starter-kit/commit/bbb5d71a7e73f77e258a8a179661b7296c43f250))
* replace dramatiq with celery + dj-control-room ([3ae8391](https://github.com/junox-systems/django-starter-kit/commit/3ae8391b4d74a5d94dbc950aad3a4edc124f2bf7))
* rewrite prod Dockerfile as multi-stage almalinux:10-kitten-minimal with uv-only ([6405e72](https://github.com/junox-systems/django-starter-kit/commit/6405e72bb9f818084d56432d2d02a2d1112cddf8))
* rm django unfold, keep stock admin as default ([1304a72](https://github.com/junox-systems/django-starter-kit/commit/1304a72ae1b07271b861f22a8d0ebf06e093b972))
* **stack:** put nginx in front of web for TLS ([90224d3](https://github.com/junox-systems/django-starter-kit/commit/90224d3d95bb1d00a46285f5f1f00ce846e5441f))
* **storage:** sign S3 media URLs with public endpoint ([b1c44d3](https://github.com/junox-systems/django-starter-kit/commit/b1c44d3462f61d8de791fb963e128667cecacf55))
* style all allauth pages, add profile page ([aceece8](https://github.com/junox-systems/django-starter-kit/commit/aceece8a995d55c05dccaf8e59714be7a393e6ba))
* swap daisyui for basecoat css and theme system ([4f314be](https://github.com/junox-systems/django-starter-kit/commit/4f314be834b5a7f5645dce888145f9501fb00d9d))
* **tasks:** replace celery with django-q2 on ORM broker ([d768a6a](https://github.com/junox-systems/django-starter-kit/commit/d768a6a96bc626374a848e055e012c6c57a65327))
* **users:** add data export and account deletion ([a41646b](https://github.com/junox-systems/django-starter-kit/commit/a41646b7d67bae46faf3d63ac631c8a602fa6ddd))
* **users:** queue welcome email on signup ([4282e40](https://github.com/junox-systems/django-starter-kit/commit/4282e409cb1080c580b2e83c36075790a2be6faf))


### Bug Fixes

* add S3 partial config warning, widen hash regex, document CONN_MAX_AGE ([21a9777](https://github.com/junox-systems/django-starter-kit/commit/21a97775aee5d8d4f18f04962f291e718966b3af))
* add settings guard in asgi.py, fix Makefile prod-start ([126c259](https://github.com/junox-systems/django-starter-kit/commit/126c25967331bb451218b32a26d72530aa04532f))
* address final review findings — swarm depends_on list, OTEL_ENABLED, stack-deploy IMAGE_NAME, settings module env, worker healthcheck, init.sh probe ([1f9d807](https://github.com/junox-systems/django-starter-kit/commit/1f9d8071bc018b4df33833ec907df7ee06abe9f6))
* **api:** restrict user endpoints, repair detail route ([83333a9](https://github.com/junox-systems/django-starter-kit/commit/83333a97fa4dd43b1730b83c6f5bfc46e80f7170))
* **ci:** call existing recipes via just, build frontend ([2023f29](https://github.com/junox-systems/django-starter-kit/commit/2023f290cb29ad3099be0ba2029943c4c3380abe))
* clean DMR_SETTINGS override, document SSL/HSTS setup ([e29655b](https://github.com/junox-systems/django-starter-kit/commit/e29655be3fd938a6c0ca83438bdcfaf863e7fa87))
* clickstack local mode — no login required ([7ea53bf](https://github.com/junox-systems/django-starter-kit/commit/7ea53bf84e81bed77613571fa26c506d25802989))
* **deps:** pin django 5.2.18, bump minor deps ([f74cd99](https://github.com/junox-systems/django-starter-kit/commit/f74cd99d7bc569b082e5f0e8ec07250877c28fed))
* **dev:** run migrations on container start ([fed65b2](https://github.com/junox-systems/django-starter-kit/commit/fed65b2b7dbbea02373fd7bf3bfeb64f3103b7c4))
* **dev:** wait for healthy db, drop unused S3, gate OTEL ([b5d69bc](https://github.com/junox-systems/django-starter-kit/commit/b5d69bc34917fa63a746bd2b47c9d97e937e6e90))
* **docker:** stop uv run installing dev deps at runtime ([7648233](https://github.com/junox-systems/django-starter-kit/commit/76482336ac84b5e256d66ee6c0e6c3282a7aa487))
* **frontend:** connect theme toggle in app shell ([17208d9](https://github.com/junox-systems/django-starter-kit/commit/17208d9f416fe4d7dd9baf375e4e66146418ae87))
* link frontend traces to backend via asgi middleware ([566c3a9](https://github.com/junox-systems/django-starter-kit/commit/566c3a95f065eb709cfa9dd78c082ebf0456fc7a))
* **mfa:** show TOTP QR code in dark mode ([8a13cdb](https://github.com/junox-systems/django-starter-kit/commit/8a13cdb6db3ed11433f0212816a55fb56aed2eff))
* **prod:** healthcheck /healthz/ instead of an open port ([f9b9106](https://github.com/junox-systems/django-starter-kit/commit/f9b910631fe2e46b52320684ecd00dacbfc9b073))
* **prod:** require CSRF origins and verified sender ([358ab14](https://github.com/junox-systems/django-starter-kit/commit/358ab148639c8575d4e57ddcf14c350ad64570e6))
* **prod:** serialize migrations with a Postgres advisory lock ([92f35de](https://github.com/junox-systems/django-starter-kit/commit/92f35de8091d06b50f34bd2d75bd42b91e1d7d47))
* remove .env requirement, dev uses filesystem storage ([af3e6ec](https://github.com/junox-systems/django-starter-kit/commit/af3e6eca749f9819fdf1719b372c7330f1a16af3))
* render connected accounts without a phantom empty radio ([78a0882](https://github.com/junox-systems/django-starter-kit/commit/78a08820234ec8b6db3c1b84359ab5cec0f943ef))
* resolve verification issues ([e8de5b8](https://github.com/junox-systems/django-starter-kit/commit/e8de5b804b83f2c841db682a2187caf0ff1b526c))
* **settings:** drop amazonaws domain for custom S3 endpoint ([7ba90c4](https://github.com/junox-systems/django-starter-kit/commit/7ba90c455a79771f3dde8f72e08beb24369ba6f5))
* **settings:** refuse dev SECRET_KEY in production ([069235e](https://github.com/junox-systems/django-starter-kit/commit/069235e21634f8157669eda8b8ed0306b764b7ef))
* slim runtime stage to uv+python only, dockerignore staticfiles ([d22c8c4](https://github.com/junox-systems/django-starter-kit/commit/d22c8c43fef471e4b164510fbfefb799654e3ea7))
* **test:** run e2e against built assets ([72fc78d](https://github.com/junox-systems/django-starter-kit/commit/72fc78daa7106bc8c3d9242f6d810420e94df3e0))
* update Dockerfile to python:3.14-slim ([8e63c8b](https://github.com/junox-systems/django-starter-kit/commit/8e63c8b7c7a231c84e752090560e493774fa26da))


### Performance Improvements

* lazy-load HyperDX, drop redundant manifest hashing ([5e1f655](https://github.com/junox-systems/django-starter-kit/commit/5e1f65506e92e7f75c6a47e36814189d8200066d))


### Documentation

* abstract the Django-template-to-Svelte formula in AGENTS.md ([62c3434](https://github.com/junox-systems/django-starter-kit/commit/62c34343828d207fcaa1517375e3da000ba12b9e))
* add .env.example, switch docs to just, match the stack ([cae7df7](https://github.com/junox-systems/django-starter-kit/commit/cae7df71369d6a4b8b91bb80f722af5cff79bf3d))
* add AGENTS.md for AI agents, symlink CLAUDE.md -&gt; AGENTS.md ([374793a](https://github.com/junox-systems/django-starter-kit/commit/374793aa8e28c13379e4c28c2316caf14cb200e1))
* add harden & slim design spec ([5a7da8b](https://github.com/junox-systems/django-starter-kit/commit/5a7da8bed1292600e33bbdba0ba91ed59304bb7e))
* add implementation plan for harden-and-slim ([b7bb9b0](https://github.com/junox-systems/django-starter-kit/commit/b7bb9b03c2503cdad4ebf84c722c71a1b30f2590))
* align plan expectation prose with passwordless set-password test ([c68e1d9](https://github.com/junox-systems/django-starter-kit/commit/c68e1d99e1460e117a1d070c5113023fba72e62c))
* amend plan — fix rustfs healthcheck endpoint, bucket init, .env note ([b4cd6e9](https://github.com/junox-systems/django-starter-kit/commit/b4cd6e949469e6674bf9c651fc60336323b92cec))
* **brief:** drop stale DRF placeholder notes ([ae0a8f2](https://github.com/junox-systems/django-starter-kit/commit/ae0a8f2b3a2e177f7ce47a56ae79af4488b84d01))
* design spec for allauth pages inside the dashboard shell ([9d938f5](https://github.com/junox-systems/django-starter-kit/commit/9d938f52c2481cda8801d11ac7bd106076129a50))
* document username/email normalization rationale in User model ([0f182c2](https://github.com/junox-systems/django-starter-kit/commit/0f182c258018296a0cf082067f32e824aa877116))
* drop celery-migration framing from comments ([0bd9c39](https://github.com/junox-systems/django-starter-kit/commit/0bd9c39ce0d047af1daee02445c603a1529cd822))
* implementation plan for allauth pages inside the dashboard shell ([47692ae](https://github.com/junox-systems/django-starter-kit/commit/47692aef72c6cf5de4864947af9b9d530d9b539f))
* implementation plan for allauth pages inside the dashboard shell ([a494761](https://github.com/junox-systems/django-starter-kit/commit/a494761c73f776e709fb0bdb77c92f74ddc26033))
* make the Svelte bridge self-explanatory for future readers ([11115eb](https://github.com/junox-systems/django-starter-kit/commit/11115eba7a8b97948a6b2de22ad2c861f722ed23))
* mark harden-and-slim plan complete ([e09fcf4](https://github.com/junox-systems/django-starter-kit/commit/e09fcf4194242ee6fbaf4d56bed4a889e5d0e726))
* update DEVELOPMENT.md — remove htmx references, document svelte-bridge ([e353b01](https://github.com/junox-systems/django-starter-kit/commit/e353b010c8b26943cf028cd7d595fda99d84fd05))
* update README for harden-and-slim changes ([2ff4e8b](https://github.com/junox-systems/django-starter-kit/commit/2ff4e8b94587d432b03cbee336e67266bf0600f8))
* update README for rustfs, clickstack, swarm stack ([bc5bfba](https://github.com/junox-systems/django-starter-kit/commit/bc5bfbabb3fb836d5f6ddcd446cf1c1df73caf41))


### Miscellaneous Chores

* release 0.3.0 ([9ee50eb](https://github.com/junox-systems/django-starter-kit/commit/9ee50eb6143c8e71497c8ac8f181c5120ea7f73f))


### Code Refactoring

* remove redis; postgres backs cache and settings ([e89baaf](https://github.com/junox-systems/django-starter-kit/commit/e89baaf9ef74aad0cc1415c65afe0ec3b8c3c33d))


### Build System

* **docker:** switch base images to debian trixie-slim ([5f5d504](https://github.com/junox-systems/django-starter-kit/commit/5f5d50457001ab3ab80534c7845324434f7d881a))

## [0.2.0](https://github.com/junox-systems/django-starter-kit/compare/v0.1.0...v0.2.0) (2026-05-14)


### Features

* django-unfold ([67dea2b](https://github.com/junox-systems/django-starter-kit/commit/67dea2b2963b28096c2381732c820e19bcc82f21))
* replace Django REST Framework with Django Modern REST (DMR) for API development ([317d41e](https://github.com/junox-systems/django-starter-kit/commit/317d41e8411f9bf0070cb998d70e500b98fc1df1))
* replace Django REST Framework with dmr for API controllers and OpenAPI generation ([2914f38](https://github.com/junox-systems/django-starter-kit/commit/2914f38f558429a642445365436449fda32e63c4))
* svelte v5 init ([aac2663](https://github.com/junox-systems/django-starter-kit/commit/aac2663cd6cc94dd7cd9fe7cb9095aef11a914fa))
* update project minimum Python requirement to 3.14 ([af3255f](https://github.com/junox-systems/django-starter-kit/commit/af3255f19b23b3054e3e07d007fda1b8311aacfa))
* upgrade frontend pkgs ([438351d](https://github.com/junox-systems/django-starter-kit/commit/438351d60df953bb933abfbad417d14c2867dc1f))
* use uuid v7 ([12184d3](https://github.com/junox-systems/django-starter-kit/commit/12184d32e5d169d211a0c1d0eb275af4d4a0d00b))

## 0.1.0 (2025-08-27)


### Features

* add turbo helper, enable turbo globally, work with debug toolbar ([6c7c7b7](https://github.com/junoxlabs/django-starter-kit/commit/6c7c7b7bcd1317429f31f35eca1d1bc9dac93b9e))
* dev compose for db, rabbitmq, s3 and redis ([7d47877](https://github.com/junoxlabs/django-starter-kit/commit/7d47877481bad5e2d7fb8d00d4dc0f0d97b89731))
* improved BRIEF.md ([4182b4f](https://github.com/junoxlabs/django-starter-kit/commit/4182b4f8bd41d91d029acdc8bb5768308cd7c4b6))
* integrate opentelemetry ([89879e3](https://github.com/junoxlabs/django-starter-kit/commit/89879e3c017bcc2a585883cfc2159aa100cd7d83))
* makefile, uvloop for async in granian ([cd5aac5](https://github.com/junoxlabs/django-starter-kit/commit/cd5aac534c3aaefe8ad09761a5e21e025b75cfbf))
* more useful users model ([55b3625](https://github.com/junoxlabs/django-starter-kit/commit/55b3625a8614aaa26efee0f1d8deed150023444d))
* pages app for pages ([9bf1f0b](https://github.com/junoxlabs/django-starter-kit/commit/9bf1f0bbf63c4e0c7740d0566d2c96ea0ae1c671))
* reproducible dev environment; docs; ([52cf1a6](https://github.com/junoxlabs/django-starter-kit/commit/52cf1a6ca6a36078cbb636d2455e48ecb0fa0a07))
* update psycopg to v3 ([39e211b](https://github.com/junoxlabs/django-starter-kit/commit/39e211b200c237acc358b5200b0dcaa6f0666cd7))
* upgrade frontend to latest ([727e3c9](https://github.com/junoxlabs/django-starter-kit/commit/727e3c9cb27f55fbef2fe2c4b2e5e9cb6d3f0869))
* vite, frontend working on prod and dev ([e234027](https://github.com/junoxlabs/django-starter-kit/commit/e234027d2fe85903938d2b5d7e6dbea2eb708c72))
* working django init ([40db5ef](https://github.com/junoxlabs/django-starter-kit/commit/40db5ef096c4568c297f9a04654eaaf63e12e8ea))


### Bug Fixes

* debug_toolbar on prod, 400 error on prod ([929707f](https://github.com/junoxlabs/django-starter-kit/commit/929707fa206c358b05aef2b6ba657f4bb2253326))
* dependencies on dev environment (docker) not working ([b30ef41](https://github.com/junoxlabs/django-starter-kit/commit/b30ef41ee139e567e2a0763e541a0b013bf64b21))
* django-vite, vite working on dev server ([1ef4a96](https://github.com/junoxlabs/django-starter-kit/commit/1ef4a96e1d7c78fecf4bf1ad656e763cc93bec34))
* fmt; versions; paradedb instead of base pg ([8288b3b](https://github.com/junoxlabs/django-starter-kit/commit/8288b3b7883d71d2b8ca6783a65f705a381283f8))
* stop turbo drive, vite auto import controllers ([7649298](https://github.com/junoxlabs/django-starter-kit/commit/7649298221b22232f4b002649ec7898d6f7b91e9))
