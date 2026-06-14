# Local npm

This workspace keeps a local npm entrypoint because the Codex shell may not have system `node` or `npm` on `PATH`.

Use it before running frontend scripts:

```sh
source tools/npm/use-npm.sh
npm -v
```

From `frontend/`:

```sh
source ../tools/npm/use-npm.sh
npm run test
npm run build
```

If `tools/npm/package/` is missing, reinstall the local npm package:

```sh
tools/npm/install-npm.sh
```

The npm package and cache are local generated dependencies and are ignored by Git.
