from commands.ultimapartida import register_ultimapartida
from commands.analizarpartida import register_analizarpartida
from commands.historialpartidas import register_historialpartidas
from commands.matchups import register_matchups
from commands.worstgames import register_worstgames
from commands.dbstats import register_dbstats
from commands.duracionpartidas import register_duracionpartidas


def register_all_commands(tree):
    register_ultimapartida(tree)
    register_analizarpartida(tree)
    register_historialpartidas(tree)
    register_matchups(tree)
    register_worstgames(tree)
    register_dbstats(tree)
    register_duracionpartidas(tree)


# Alias used by bot.py
register_commands = register_all_commands
