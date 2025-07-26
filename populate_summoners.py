#!/usr/bin/env python3
"""
Script para popular la base de datos con summoners específicos
"""

import sys
import os
sys.path.append('.')

from database import save_summoner, get_summoners_for_autocomplete, get_summoner_stats

def populate_summoners():
    """Popula la base de datos con summoners específicos"""
    
    summoners = [
        "BichoPower#LAN",
        "SoyMaloNoTroll#SAM", 
        "Deathscythe#Snake",
        "RompehOrtz#LAN",
        "Legnayos1023#TTV",
        "Feanen#LAN",
        "darkim31#LAN",
        "VenEkko#PETE"
    ]
    
    print("🎮 Populando base de datos con summoners...")
    print("=" * 50)
    
    # Guardar cada summoner
    for summoner in summoners:
        try:
            save_summoner(summoner)
            print(f"✅ {summoner}")
        except Exception as e:
            print(f"❌ Error con {summoner}: {e}")
    
    print("\n" + "=" * 50)
    
    # Simular búsquedas adicionales para algunos summoners (popularidad)
    popular_searches = {
        "BichoPower#LAN": 5,
        "Feanen#LAN": 3,
        "RompehOrtz#LAN": 4,
        "darkim31#LAN": 2
    }
    
    print("📈 Simulando búsquedas adicionales para popularidad...")
    for summoner, count in popular_searches.items():
        for _ in range(count):
            save_summoner(summoner)
        print(f"🔥 {summoner}: {count + 1} búsquedas totales")
    
    print("\n" + "=" * 50)
    
    # Mostrar estadísticas finales
    stats = get_summoner_stats()
    print(f"📊 Total summoners: {stats['total_summoners']}")
    print(f"📊 Total búsquedas: {stats['total_searches']}")
    
    # Mostrar top summoners
    print("\n🏆 Top summoners por popularidad:")
    top_summoners = get_summoners_for_autocomplete("", 10)
    for i, summoner in enumerate(top_summoners, 1):
        print(f"   {i}. {summoner}")
    
    print("\n✅ ¡Base de datos populada exitosamente!")
    
    # Probar autocompletado con algunos filtros
    print("\n🔍 Probando autocompletado:")
    test_filters = ["Bicho", "Feanen", "LAN", "darkim"]
    for filter_text in test_filters:
        results = get_summoners_for_autocomplete(filter_text, 5)
        print(f"   '{filter_text}': {results}")

if __name__ == "__main__":
    populate_summoners()
