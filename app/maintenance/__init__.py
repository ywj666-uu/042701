from flask import Blueprint

maintenance = Blueprint('maintenance', __name__)

from . import views
