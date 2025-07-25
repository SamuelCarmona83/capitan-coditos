from .ultimapartida import register_ultimapartida
from .analizarpartida import register_analizarpartida

def register_commands(tree):
    register_ultimapartida(tree)
    register_analizarpartida(tree)
