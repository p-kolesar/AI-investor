import json
import logging

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness probe used by the deploy pipeline smoke test."""
    logging.info("Health check requested.")
    return func.HttpResponse(
        body=json.dumps({"status": "ok"}),
        mimetype="application/json",
        status_code=200,
    )
