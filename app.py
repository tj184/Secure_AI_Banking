
import os
import logging
from functools import wraps

from flask import (
    Flask,
    request,
    jsonify,
    session,
)

from config import Config

# Set environment variables before importing modules that initialize
# the database engine or Ollama model.
os.environ.setdefault("DATABASE_URL", Config.DATABASE_URL)
os.environ.setdefault("OLLAMA_BASE_URL", Config.OLLAMA_BASE_URL)
os.environ.setdefault("OLLAMA_MODEL", Config.OLLAMA_MODEL)

from database.db import init_db, check_db_connection

from agents.supervisor_agent import run_supervisor

from security.authentication import (
    register_customer,
    authenticate_customer,
    establish_session,
    create_user_context,
    logout_user,
)

from hooks.before_agent import (
    before_agent,
    GuardrailViolation,
)

from hooks.after_agent import after_agent

from monitoring.audit_logger import log_event

from monitoring.guardrail_metrics import increment_metric


# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("securebank.app")


# ---------------------------------------------------------
# FLASK APPLICATION FACTORY
# ---------------------------------------------------------

def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    # Initialize database tables
    with app.app_context():
        init_db()

    # -----------------------------------------------------
    # HELPER FUNCTIONS
    # -----------------------------------------------------

    def get_authenticated_context():

        context = create_user_context()

        if not isinstance(context, dict):
            return None

        if not context.get("authenticated"):
            return None

        return context
    @app.route("/", methods=["GET"])
    def home():
        return jsonify({
            "application": "SecureBank AI",
            "status": "running",
            "message": "Welcome to SecureBank AI",
            "endpoints": {
                "health": "/health",
                "register": "/api/register",
                "login": "/api/login",
                "profile": "/api/me",
                "chat": "/api/chat",
                "logout": "/api/logout"
            }
        }), 200

    def login_required_api(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            context = get_authenticated_context()

            if not context:
                return jsonify({
                    "success": False,
                    "message": "Authentication required.",
                }), 401

            return func(context, *args, **kwargs)

        return wrapper

    
    def get_auth_principal(auth_result):
        """Extract the authenticated principal from the auth result."""

        if not isinstance(auth_result, dict):
            return None

        if auth_result.get("success") is not True:
            return None

        principal = (
            auth_result.get("principal")
            or auth_result.get("customer")
            or auth_result.get("user")
        )

        if not isinstance(principal, dict):
            return None

        role = principal.get("role")

        if role == "customer":
            customer_id = principal.get("customer_id")

            if (
                not isinstance(customer_id, int)
                or isinstance(customer_id, bool)
                or customer_id <= 0
            ):
                return None

        elif role == "manager":
            manager_id = principal.get("manager_id")

            if (
                not isinstance(manager_id, int)
                or isinstance(manager_id, bool)
                or manager_id <= 0
            ):
                return None

        else:
            return None

        return principal

    # -----------------------------------------------------
    # HEALTH CHECK
    # -----------------------------------------------------

    @app.route("/health", methods=["GET"])
    def health():

        try:
            database_status = check_db_connection()

            return jsonify({
                "success": True,
                "application": "SecureBank AI",
                "database": "connected" if database_status else "unavailable",
                "model": app.config["OLLAMA_MODEL"],
            }), 200

        except Exception:

            logger.exception("Health check failed.")

            return jsonify({
                "success": False,
                "application": "SecureBank AI",
                "database": "unavailable",
            }), 503

    # -----------------------------------------------------
    # CUSTOMER REGISTRATION
    # -----------------------------------------------------

    @app.route("/api/register", methods=["POST"])
    def register():

        data = request.get_json(silent=True) or {}

        full_name = data.get("full_name")
        email = data.get("email")
        password = data.get("password")
        phone = data.get("phone")

        if not full_name or not email or not password:

            return jsonify({
                "success": False,
                "message": "Full name, email and password are required.",
            }), 400

        try:

            result = register_customer(
                full_name=full_name,
                email=email,
                password=password,
                phone=phone,
            )

            if isinstance(result, dict) and result.get("success") is False:

                return jsonify({
                    "success": False,
                    "message": result.get(
                        "message",
                        "Registration failed.",
                    ),
                }), 400

            return jsonify({
                "success": True,
                "message": "Customer registration completed.",
            }), 201

        except Exception:

            logger.exception("Customer registration failed.")

            return jsonify({
                "success": False,
                "message": "Registration could not be completed.",
            }), 500

    # -----------------------------------------------------
    # CUSTOMER LOGIN
    # -----------------------------------------------------

    @app.route("/api/login", methods=["POST"])
    def login():

        data = request.get_json(silent=True) or {}

        email = data.get("email")
        password = data.get("password")

        if not email or not password:

            return jsonify({
                "success": False,
                "message": "Email and password are required.",
            }), 400

        try:

            auth_result = authenticate_customer(
                email=email,
                password=password,
            )

            principal = get_auth_principal(auth_result)

            if not principal:

                increment_metric("authentication_failures")

                return jsonify({
                    "success": False,
                    "message": "Invalid email or password.",
                }), 401

            # Prevent session fixation by replacing the session.
            session.clear()

            establish_session(principal)

            session.permanent = True

            context = create_user_context()

            if not context or not context.get("authenticated"):

                session.clear()

                return jsonify({
                    "success": False,
                    "message": "Could not establish an authenticated session.",
                }), 500

            log_event(
                action="customer_login",
                status="SUCCESS",
                customer_id=context.get("customer_id"),
                agent_name="authentication",
                details="Customer authenticated successfully.",
            )

            return jsonify({
                "success": True,
                "message": "Login successful.",
                "customer": {
                    "customer_id": context.get("customer_id"),
                    "full_name": context.get("full_name"),
                    "email": context.get("email"),
                },
            }), 200

        except Exception:

            logger.exception("Customer login failed.")

            increment_metric("authentication_failures")

            return jsonify({
                "success": False,
                "message": "Login could not be completed.",
            }), 500

    # -----------------------------------------------------
    # CUSTOMER LOGOUT
    # -----------------------------------------------------

    @app.route("/api/logout", methods=["POST"])
    def logout():

        context = get_authenticated_context()

        logout_user()

        log_event(
            action="customer_logout",
            status="SUCCESS",
            customer_id=(
                context.get("customer_id") if context else None
            ),
            agent_name="authentication",
            details="Session terminated.",
        )

        return jsonify({
            "success": True,
            "message": "Logged out successfully.",
        }), 200

    # -----------------------------------------------------
    # CURRENT CUSTOMER
    # -----------------------------------------------------

    @app.route("/api/me", methods=["GET"])
    @login_required_api
    def current_customer(context):

        return jsonify({
            "success": True,
            "customer": {
                "customer_id": context.get("customer_id"),
                "full_name": context.get("full_name"),
                "email": context.get("email"),
                "role": context.get("role"),
            },
        }), 200

    # -----------------------------------------------------
    # BANKING AI CHAT
    # -----------------------------------------------------

    @app.route("/api/chat", methods=["POST"])
    @login_required_api
    def chat(context):

        data = request.get_json(silent=True) or {}

        query = data.get("message")

        if not isinstance(query, str) or not query.strip():

            return jsonify({
                "success": False,
                "message": "Please provide a valid message.",
            }), 400

        try:

            # 1. Run input guardrails
            precheck = before_agent(
                query=query,
                user_context=context,
            )

            # 2. Run supervisor and selected banking agent
            supervisor_result = run_supervisor(
                query=precheck["query"],
                user_context=context,
            )

            if not isinstance(supervisor_result, dict):

                raise RuntimeError(
                    "Unexpected supervisor response."
                )

            agent_response = supervisor_result.get("response", "")

            selected_agent = supervisor_result.get(
                "selected_agent",
                "unknown",
            )

            # 3. Validate and sanitize generated response
            postcheck = after_agent(
                response=agent_response,
                agent_name=selected_agent,
                user_context=context,
            )

            # 4. Return safe result
            if not postcheck.get("allowed"):

                return jsonify({
                    "success": False,
                    "message": postcheck["response"],
                    "reason": postcheck.get("reason"),
                }), 200

            # 5. Audit event
            log_event(
                action="agent_request",
                status="SUCCESS",
                customer_id=context.get("customer_id"),
                agent_name=selected_agent,
                details="Banking assistant request processed.",
            )

            return jsonify({
                "success": True,
                "agent": selected_agent,
                "response": postcheck["response"],
                "pii_detected": postcheck.get("pii_detected", False),
            }), 200

        except GuardrailViolation as exc:

            logger.warning(
                "Request blocked by guardrails. reason=%s",
                exc.reason,
            )

            log_event(
                action="agent_request_blocked",
                status="BLOCKED",
                customer_id=context.get("customer_id"),
                agent_name="guardrails",
                details=f"Reason: {exc.reason}",
            )

            return jsonify({
                "success": False,
                "message": str(exc),
                "reason": exc.reason,
            }), 400

        except Exception:

            logger.exception("Banking chat request failed.")

            log_event(
                action="agent_request",
                status="ERROR",
                customer_id=context.get("customer_id"),
                agent_name="supervisor",
                details="An internal error occurred.",
            )

            return jsonify({
                "success": False,
                "message": "An internal error occurred. Please try again.",
            }), 500

    # -----------------------------------------------------
    # GLOBAL ERROR HANDLERS
    # -----------------------------------------------------

    @app.errorhandler(404)
    def not_found(error):

        return jsonify({
            "success": False,
            "message": "Endpoint not found.",
        }), 404

    @app.errorhandler(413)
    def request_too_large(error):

        return jsonify({
            "success": False,
            "message": "Request is too large.",
        }), 413

    @app.errorhandler(500)
    def internal_error(error):

        logger.exception("Unhandled application error.")

        return jsonify({
            "success": False,
            "message": "Internal server error.",
        }), 500

    return app


# ---------------------------------------------------------
# APPLICATION ENTRY POINT
# ---------------------------------------------------------

app = create_app()


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=app.config["DEBUG"],
    )
