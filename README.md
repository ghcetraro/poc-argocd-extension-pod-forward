# ArgoCD Extension Pod Forward - Backend

Backend proxy para la extensión de Port Forward de ArgoCD. Este servicio permite hacer port-forward a pods desde la UI de ArgoCD.

## Descripción

Este backend expone un API REST que permite:
- Iniciar port-forward a pods de Kubernetes
- Gestionar múltiples port-forwards simultáneos
- Detener port-forwards activos
- Consultar el estado de port-forwards activos

## Estructura

```
argocd-extension-pod-forward/
├── app.py              # Aplicación Flask principal
├── requirements.txt    # Dependencias Python
├── Dockerfile          # Imagen Docker (opcional)
├── deployment.yaml     # Manifiestos de Kubernetes
└── README.md          # Este archivo
```

## Instalación

### Opción 1: Usando kubectl directamente

```bash
cd argocd-helm/applicationset/argocd-extension-pod-forward

# Aplicar los manifiestos
kubectl apply -f deployment.yaml
```

### Opción 2: Usando ApplicationSet (si lo creas)

Crear un ApplicationSet que despliegue este backend automáticamente.

## Verificación

```bash
# Verificar que el deployment esté corriendo
kubectl get deployment argocd-extension-pod-forward -n argocd

# Verificar el servicio
kubectl get service argocd-extension-pod-forward -n argocd

# Ver logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-extension-pod-forward

# Probar health check
kubectl port-forward -n argocd svc/argocd-extension-pod-forward 8080:80
curl http://localhost:8080/health
```

## API Endpoints

### Health Check
```
GET /health
```

### Iniciar Port Forward
```
GET /api/v1/extensions/pod-forward/forward?namespace=<namespace>&pod=<pod-name>&port=<port>
```

### Detener Port Forward
```
POST /api/v1/extensions/pod-forward/stop/<session_id>
```

### Estado de Port Forwards
```
GET /api/v1/extensions/pod-forward/status
```

## Configuración

El backend se configura mediante variables de entorno:

- `PORT`: Puerto donde escucha el servidor (default: 8080)
- `ARGOCD_SERVER_URL`: URL del servidor de ArgoCD
- `FORWARD_TIMEOUT`: Tiempo de vida de los port-forwards en segundos (default: 3600)
- `KUBECTL_NAMESPACE`: Namespace donde corre el proxy (default: argocd)

## RBAC

El backend necesita permisos para:
- Listar y obtener pods
- Crear port-forwards

Estos permisos están configurados en el `Role` y `RoleBinding` del deployment.

## Notas

- El backend usa kubectl para hacer port-forward
- Los port-forwards se ejecutan dentro del contenedor del backend
- Cada port-forward tiene un timeout configurable
- El backend puede manejar múltiples port-forwards simultáneos
