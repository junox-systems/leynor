# Changelog

## [0.2.0](https://github.com/junox-systems/leynor/compare/v0.1.0...v0.2.0) (2026-11-09)


### ⚠ BREAKING CHANGES

* **runs:** APP_ARTIFACT_ROOT is gone. The stack needs APP_ARTIFACT_ACCESS_KEY and APP_ARTIFACT_SECRET_KEY. Files under the old artifacts volume are not migrated.

### Features

* add the heavy worker and pipeline settings ([bf57ece](https://github.com/junox-systems/leynor/commit/bf57ececf68c2428c24aad945635807407992e0f))
* adopt the leynor Django kit as the app base ([8b6158d](https://github.com/junox-systems/leynor/commit/8b6158d86bfa46ed51ac19b421e54c47338bbf0c))
* **ai:** configure providers, models and steps in admin ([58cdef6](https://github.com/junox-systems/leynor/commit/58cdef604db1616f9e2fa08a02671bf1dab9e87d))
* **brands:** give a brand its audiences ([24bf1f5](https://github.com/junox-systems/leynor/commit/24bf1f5d99921e3f0f29f5575873484827c18ff9))
* **brands:** give projects an optional brand client ([92d3649](https://github.com/junox-systems/leynor/commit/92d3649dd9044cb2c8e364c936b71bb58424387f))
* **campaigns:** let every output carry its own prompt and goal ([8509013](https://github.com/junox-systems/leynor/commit/85090137d82a07b6a2a2bab1579efcd21aa54707))
* **campaigns:** point a campaign at one of the brand's audiences ([3bd0c22](https://github.com/junox-systems/leynor/commit/3bd0c223eb608f3af7b8bd62e4acbd13c34b8574))
* **campaigns:** state the campaign goal in words, keep the unit outcome ([34d2971](https://github.com/junox-systems/leynor/commit/34d29711547086dc804ef4a013af62e11fab4ac4))
* **channels:** scaffold channel units and publishing skeleton ([c956284](https://github.com/junox-systems/leynor/commit/c9562846f26623faa098edc4d69de4d65cd3174d))
* **instagram:** turn an idea into a reel through three takes ([db3e7b7](https://github.com/junox-systems/leynor/commit/db3e7b77f4e150b35bc25eba44314019dd17172c))
* **instagram:** turn an idea into a reel through three takes ([5deeaa4](https://github.com/junox-systems/leynor/commit/5deeaa4eb1551f6ecbb8f5dc9636c1dc2aad1532))
* **projects:** add reel pages and gate decisions ([3f7dc98](https://github.com/junox-systems/leynor/commit/3f7dc98f9f82e1110ec491f7b6e0ad86ee85568a))
* **projects:** model the six-gate reel route ([143b36c](https://github.com/junox-systems/leynor/commit/143b36c69aa21c6a64e59ce28d1f063f711d687b))
* **projects:** move the content spec into the app ([93ad023](https://github.com/junox-systems/leynor/commit/93ad02380b5731f0edae0410164ddd7be0727520))
* **projects:** store a client, description and status ([6215b44](https://github.com/junox-systems/leynor/commit/6215b44d4451c1456e2ec7289a78b0c2ea8210f4))
* **reels:** make the reel a prompt, a goal and a length ([7fbbfa3](https://github.com/junox-systems/leynor/commit/7fbbfa368c4ab2a3508c884b9925b48a81e6b443))
* **runs:** add artifact store with path guards ([f061161](https://github.com/junox-systems/leynor/commit/f0611610c330128b427b053517b3781f3ed181e1))
* **runs:** keep reel artifacts in S3 storage everywhere ([0f50242](https://github.com/junox-systems/leynor/commit/0f50242237ff379d93dcf838a46d959b6f2e40d9))
* **runs:** keep reel artifacts in S3 storage everywhere ([32e6d23](https://github.com/junox-systems/leynor/commit/32e6d2300211eeebe5473d87f5fa2df9facff56c))
* **runs:** only check the artifacts bucket in production ([160f815](https://github.com/junox-systems/leynor/commit/160f81546c441065e5db7a38494ee49a268edf28))
* **runs:** point artifact storage at AWS by default ([1369819](https://github.com/junox-systems/leynor/commit/1369819992aefac6926dd13e40b531102f451895))


### Bug Fixes

* **campaigns:** cast the old audience text instead of retyping it ([9a91f62](https://github.com/junox-systems/leynor/commit/9a91f621cdb5f2df95f6efb3ca8a0bbcb2eed698))
* **campaigns:** name the audience relation the model declares ([2bbe0e0](https://github.com/junox-systems/leynor/commit/2bbe0e03d4f79714d46406a9c4d0486cc3c945a9))
* **campaigns:** run the audience migration outside one transaction ([0a7064a](https://github.com/junox-systems/leynor/commit/0a7064a49b94e968152581d8937fd81a32b9c005))
* **ci:** probe the sign-in page in the prod smoke test ([0a9a74e](https://github.com/junox-systems/leynor/commit/0a9a74e4973f3267cec8452ebaf6032d9a5a672c))
* **deploy:** flatten swarm interpolation in the stack file ([6ac260d](https://github.com/junox-systems/leynor/commit/6ac260dda2e91c4c0f57f2eaa3b3ea3ef4fe7033))
* **dev:** drop the last database name hardcoded as "db" ([6b17919](https://github.com/junox-systems/leynor/commit/6b179193a6ccb2f64fd30674f99ef3dbe5ae4269))
* **dev:** make node and hyperframes resolvable in the heavy image ([91c04e3](https://github.com/junox-systems/leynor/commit/91c04e38660bf857d25778eaadda2553e0894dd3))
* **dev:** namespace the dev stack by app slug ([496d21a](https://github.com/junox-systems/leynor/commit/496d21a0d1a61dc083cf78c550174909239bb249))
* **dev:** own supervisor in the image, not in the project venv ([8ab94fd](https://github.com/junox-systems/leynor/commit/8ab94fd497aa7b4678639a693680597c42d35995))
* **docs:** keep arch.md a symlink to the playbook ([a88ae98](https://github.com/junox-systems/leynor/commit/a88ae98f231949b011cca99d695da7eec8106962))
* **instagram:** answer 404 when a reel file vanishes mid-request ([32f67c9](https://github.com/junox-systems/leynor/commit/32f67c913685e62db21a80ab3bfb5fbc8b78b31f))
* **instagram:** refuse Print when the voice has no checksum ([d04c401](https://github.com/junox-systems/leynor/commit/d04c401ca0635a6ea533b84dff5eb92f444eb0f1))
* **runs:** keep the old artifact if an S3 overwrite fails ([f1a7f63](https://github.com/junox-systems/leynor/commit/f1a7f63c2a8336d63528200a5b6126f6bab6d19d))
* **runs:** retry bucket creation while the store starts ([1f1c270](https://github.com/junox-systems/leynor/commit/1f1c2707c201170a46e5dd3ca5e748d19b7566e2))


### Performance Improvements

* **instagram:** fetch only the requested byte range from S3 ([93f000d](https://github.com/junox-systems/leynor/commit/93f000d2f68bf8e21bc9b1647195748f6e5f3b85))


### Documentation

* describe the reel apps in the agent guide ([9e85cb4](https://github.com/junox-systems/leynor/commit/9e85cb47573fa170d66f7d8e5fb2ef15f13278f8))
* **env:** spell out artifact bucket rules for production ([16eb8bf](https://github.com/junox-systems/leynor/commit/16eb8bfcd5fd85c39c6b7452b0143f3e4d0cd462))
* record phases 0 to 2 and what they proved ([ae9c94d](https://github.com/junox-systems/leynor/commit/ae9c94d05734fadc86386417360bd467bc45d149))
* record the domain vocabulary and three decisions ([83e2408](https://github.com/junox-systems/leynor/commit/83e24080ad7de1cf0dfbbc33ca22c0b4c12d7f8a))
* SeaweedFS is dev and CI only; prod uses its own S3 bucket ([e7da766](https://github.com/junox-systems/leynor/commit/e7da7662d311c2c1fd03b02886f4536f12b9934b))
