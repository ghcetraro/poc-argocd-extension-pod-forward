# GitHub CI/CD para Backend Pod Forward

Este documento describe el workflow de GitHub Actions que construye y publica la imagen Docker del backend.

## Workflow

El workflow se encuentra en `.github/workflows/build-and-push.yml` y se ejecuta automáticamente cuando:

- Se hace push a las ramas `main` o `master`
- Se crea un Pull Request hacia `main` o `master`
- Se crea un Release (tag)
- Se ejecuta manualmente desde la UI de GitHub Actions

## Imagen Docker

La imagen se publica en GitHub Container Registry (GHCR):

- **Registry:** `ghcr.io`
- **Imagen:** `ghcr.io/cetraro-io/poc-argocd-forward`
- **Tags:**
  - `latest` - Para la rama principal
  - `main` o `master` - Para la rama correspondiente
  - `v1.0.0` - Para releases (semver)
  - `1.0` - Versión mayor.minor
  - `1` - Versión mayor
  - `main-<sha>` - SHA del commit para la rama

## Permisos Requeridos

El workflow necesita los siguientes permisos:

- `contents: read` - Para leer el código
- `packages: write` - Para publicar en GHCR

Estos permisos se configuran automáticamente usando `GITHUB_TOKEN`.

## Uso Local

Para construir la imagen localmente:

```bash
cd poc-argocd-extension-pod-forward
docker build -t ghcr.io/cetraro-io/poc-argocd-forward:latest .
```

## Verificación

Después de que el workflow se ejecute, puedes verificar la imagen:

```bash
# Ver las imágenes publicadas
gh api /orgs/cetraro-io/packages/container/poc-argocd-forward/versions

# O desde la UI de GitHub:
# https://github.com/orgs/cetraro-io/packages/container/poc-argocd-forward
```

## Configuración en Kubernetes

La imagen se usa en `argocd/values.yaml`:

```yaml
image: ghcr.io/cetraro-io/poc-argocd-forward:latest
imagePullPolicy: Always
```

Si el registry es privado, necesitarás crear un secret:

```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=<tu-usuario-github> \
  --docker-password=<tu-token-github> \
  -n argocd
```

Y agregar en `values.yaml`:

```yaml
imagePullSecrets:
  - name: ghcr-secret
```
