from .ultimapartida import register_ultimapartida
from .analizarpartida import register_analizarpartida
from .historialpartidas import register_historialpartidas
from .dbstats import register_dbstats

def register_commands(tree):
    register_ultimapartida(tree)
    register_analizarpartida(tree)
    register_historialpartidas(tree)
    register_dbstats(tree)
