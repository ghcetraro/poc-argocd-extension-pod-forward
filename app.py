#!/usr/bin/env python3
"""
Backend proxy para Port Forward de ArgoCD Extension
Permite hacer port-forward a pods desde la UI de ArgoCD
"""

import os
import subprocess
import threading
import time
import logging
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)  # Permitir CORS para que ArgoCD pueda hacer peticiones

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Almacenar procesos de port-forward activos
active_forwards = {}
forward_lock = threading.Lock()

# Configuración
ARGOCD_SERVER_URL = os.environ.get('ARGOCD_SERVER_URL', 'https://argocd.devops.cetraro.io')
FORWARD_TIMEOUT = int(os.environ.get('FORWARD_TIMEOUT', '3600'))  # 1 hora por defecto
KUBECTL_NAMESPACE = os.environ.get('KUBECTL_NAMESPACE', 'argocd')

logger.info(f"Backend iniciado. ArgoCD URL: {ARGOCD_SERVER_URL}, Timeout: {FORWARD_TIMEOUT}s")


def start_port_forward(namespace: str, pod_name: str, pod_port: int, local_port: int) -> subprocess.Popen:
    """Inicia un port-forward usando kubectl"""
    try:
        cmd = [
            'kubectl', 'port-forward',
            f'pod/{pod_name}',
            f'{local_port}:{pod_port}',
            '-n', namespace,
            '--address', '0.0.0.0'  # Escuchar en todas las interfaces
        ]
        
        logger.info(f"Iniciando port-forward: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Esperar un momento para verificar que el proceso inició correctamente
        time.sleep(1)
        if process.poll() is not None:
            # El proceso terminó inmediatamente, hubo un error
            stderr = process.stderr.read() if process.stderr else "Unknown error"
            logger.error(f"Error al iniciar port-forward: {stderr}")
            return None
        
        logger.info(f"Port-forward iniciado exitosamente: {pod_name}:{pod_port} -> localhost:{local_port}")
        return process
        
    except Exception as e:
        logger.error(f"Error al iniciar port-forward: {str(e)}", exc_info=True)
        return None


def stop_port_forward(session_id: str):
    """Detiene un port-forward"""
    with forward_lock:
        if session_id in active_forwards:
            process = active_forwards[session_id]['process']
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            del active_forwards[session_id]
            logger.info(f"Port-forward {session_id} detenido")


# Template HTML para mostrar el port-forward
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Port Forward - {{ pod_name }}</title>
    <meta charset="utf-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #0DADEA;
            margin-top: 0;
        }
        .info {
            background: #e8f4f8;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }
        .info p {
            margin: 5px 0;
        }
        .status {
            padding: 10px;
            border-radius: 4px;
            margin: 20px 0;
        }
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .link {
            display: inline-block;
            margin-top: 20px;
            padding: 12px 24px;
            background: #0DADEA;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
        }
        .link:hover {
            background: #0b9dd1;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 Port Forward</h1>
        <div class="info">
            <p><strong>Pod:</strong> {{ pod_name }}</p>
            <p><strong>Namespace:</strong> {{ namespace }}</p>
            <p><strong>Port:</strong> {{ port }}</p>
            <p><strong>Local Port:</strong> {{ local_port }}</p>
        </div>
        {% if status == 'error' %}
        <div class="status error">
            <strong>Error:</strong> {{ error }}
        </div>
        {% else %}
        <div class="status success">
            <strong>✅ Port-forward activo</strong>
            <p>Puedes acceder al pod en: <code>http://localhost:{{ local_port }}</code></p>
        </div>
        <a href="http://localhost:{{ local_port }}" target="_blank" class="link">
            Abrir en nueva pestaña
        </a>
        {% endif %}
    </div>
</body>
</html>
"""


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200


@app.route('/api/v1/extensions/pod-forward/forward', methods=['GET'])
def forward():
    """Endpoint principal para iniciar port-forward"""
    try:
        # Validar autenticación (opcional, ArgoCD maneja esto)
        auth_header = request.headers.get('Authorization', '')
        if not auth_header and not request.args.get('token'):
            # Permitir sin autenticación para pruebas, pero en producción deberías validar
            logger.warning("Petición sin autenticación")
        
        # Obtener parámetros
        namespace = request.args.get('namespace')
        pod_name = request.args.get('pod')
        port = int(request.args.get('port', 8080))
        
        if not namespace or not pod_name:
            return jsonify({"error": "Faltan parámetros: namespace y pod son requeridos"}), 400
        
        # Generar session ID y local port
        session_id = str(uuid.uuid4())
        local_port = 9000 + (hash(session_id) % 1000)  # Puerto entre 9000-9999
        
        # Iniciar port-forward
        process = start_port_forward(namespace, pod_name, port, local_port)
        
        if not process:
            return render_template_string(
                HTML_TEMPLATE,
                pod_name=pod_name,
                namespace=namespace,
                port=port,
                local_port=local_port,
                status='error',
                error='No se pudo iniciar el port-forward',
                session_id=session_id
            ), 500
        
        # Guardar en active_forwards
        with forward_lock:
            active_forwards[session_id] = {
                'process': process,
                'namespace': namespace,
                'pod': pod_name,
                'pod_port': port,
                'local_port': local_port,
                'started_at': time.time()
            }
        
        # Programar timeout
        def timeout_handler():
            time.sleep(FORWARD_TIMEOUT)
            stop_port_forward(session_id)
            logger.info(f"Port-forward {session_id} expirado después de {FORWARD_TIMEOUT}s")
        
        timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
        timeout_thread.start()
        
        # Retornar página HTML con información
        return render_template_string(
            HTML_TEMPLATE,
            pod_name=pod_name,
            namespace=namespace,
            port=port,
            local_port=local_port,
            status='success',
            session_id=session_id
        ), 200
        
    except Exception as e:
        logger.error(f"Error en endpoint forward: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/v1/extensions/pod-forward/stop/<session_id>', methods=['POST'])
def stop_forward(session_id):
    """Detener un port-forward"""
    try:
        stop_port_forward(session_id)
        return jsonify({"status": "stopped"}), 200
    except Exception as e:
        logger.error(f"Error al detener port-forward: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/v1/extensions/pod-forward/status', methods=['GET'])
def status():
    """Obtener estado de todos los port-forwards activos"""
    with forward_lock:
        status_list = []
        for session_id, info in active_forwards.items():
            process = info['process']
            status_list.append({
                'session_id': session_id,
                'namespace': info['namespace'],
                'pod': info['pod'],
                'pod_port': info['pod_port'],
                'local_port': info['local_port'],
                'active': process.poll() is None if process else False,
                'started_at': info['started_at']
            })
        return jsonify({"active_forwards": status_list}), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Iniciando servidor en el puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
