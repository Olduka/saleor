import uuid
import json
import logging
import requests
from django.core.cache import cache
from django.utils import timezone

from ... import ChargeStatus, TransactionKind
from ...interface import GatewayConfig, GatewayResponse, PaymentData
from .utils import generate_lipa_password, get_access_token

logger = logging.getLogger(__name__)

def dummy_success():
    return True

def _access_token(config: GatewayConfig):
    CACHE_TTL = 45 * 10
    return cache.get_or_set(
        'mpesa_auth_key', get_access_token(config),
        CACHE_TTL
    )

def get_client_token(**_):
    return str(uuid.uuid4())


def get_billing_data(payment_information: PaymentData, config: GatewayConfig):
    shortcode = config.connection_params['shortcode']
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    password = generate_lipa_password(timestamp, config)
    callback_url = config.connection_params['callback_url']
    reference = get_client_token()

    return dict(
        BusinessShortCode=shortcode,
        Password=password,
        Timestamp=timestamp,
        TransactionType="CustomerPayBillOnline",
        Amount=payment_information.amount,
        PartyA=payment_information.billing.phone,
        PartyB=shortcode,
        PhoneNumber=payment_information.billing.phone,
        CallBackURL=callback_url,
        AccountReference=reference,
        TransactionDesc="Mpesa payment"
    )


def void(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    error = None
    success = dummy_success()
    if not success:
        error = "Unable to void the transaction."
    return GatewayResponse(
        is_success=success,
        action_required=False,
        kind=TransactionKind.VOID,
        amount=payment_information.amount,
        currency=payment_information.currency,
        transaction_id=payment_information.token,
        error=error,
    )


def capture(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    """Perform capture transaction."""
    error = None
    success = False
    action_required = False
    try:
        response = requests.post(
            f"config.connection_params['base_url']mpesa/stkpush/v1/processrequest",
            headers={
                "Authorization": f"Bearer {auth_key}",
                "Content-Type": "application/json"
            },
            data=json.dumps(data)
        )
        response_data = response.json()
        response.raise_for_status()
    except Exception:
        if response_data['errorMessage'] == "Invalid Access Token":
            get_access_token(config)
            capture(payment_information, config)
        logger.warning(f"Error initiating Mpesa payment: {response_data}", exc_info=True)
        error = response_data['errorMessage']
        action_required = True
    else:
        success = True

    return GatewayResponse(
        is_success=success,
        action_required=action_required,
        kind=TransactionKind.CAPTURE,
        amount=payment_information.amount,
        currency=payment_information.currency,
        transaction_id=response_data.get('CheckoutRequestID', payment_information.token),
        error=error
    )


def confirm(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    """Perform confirm transaction."""
    error = None
    success = dummy_success()
    if not success:
        error = "Unable to process capture"

    return GatewayResponse(
        is_success=success,
        action_required=False,
        kind=TransactionKind.CAPTURE,
        amount=payment_information.amount,
        currency=payment_information.currency,
        transaction_id=payment_information.token,
        error=error
    )


def refund(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    error = None
    success = dummy_success()
    if not success:
        error = "Unable to process refund"
    return GatewayResponse(
        is_success=success,
        action_required=False,
        kind=TransactionKind.REFUND,
        amount=payment_information.amount,
        currency=payment_information.currency,
        transaction_id=payment_information.token,
        error=error,
    )


def process_payment(
    payment_information: PaymentData, config: GatewayConfig
) -> GatewayResponse:
    """Process the payment."""
    return capture(payment_information=payment_information, config=config)
