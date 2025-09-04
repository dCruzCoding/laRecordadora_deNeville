# personalidad.py
"""
Módulo de Personalidad y Textos.

Este archivo centraliza todos los textos que el bot envía al usuario.
La estructura principal es un diccionario llamado TEXTOS, donde cada clave
representa una situación o mensaje específico.

La función get_text() permite obtener un texto aleatorio de la lista
correspondiente a una clave y formatearlo con variables dinámicas.
"""

import random
from typing import Dict, List

# =============================================================================
# DICCIONARIO PRINCIPAL DE TEXTOS
# =============================================================================

TEXTOS: Dict[str, List[str]] = {

    # -------------------------------------------------------------------------
    # --- FLujo 1: Bienvenida (Onboarding) y Textos Informativos
    # -------------------------------------------------------------------------
    "onboarding_presentacion": [
        "¡Anda! A buenas horas. A ti te estaba esperando. Ya me dijo mi nieto Neville que le había dejado su recordadora a uno de sus amigos.\n\n"
        "Soy Augusta Longbottom 👵. Bueno, una huella de su personalidad que guardó en esta recordadora para que tratara a su nieto con el _cariño_ que merecía.\n\n" 
        "Mi misión es asegurarme de que no se te olvide nada importante. ¡Y más te vale hacerme caso!"
    ],
    "onboarding_informacion": [
        "*La Recordadora* 🔮 es una herramienta mágica que te ayudará a recordar tus tareas y compromisos. Es muy fácil de usar:\n\n"
        "➕📝 *AÑADIR RECORDATORIO:*\n"
        "Usa el comando /recordar. Por ejemplo:\n"
        "`/recordar mañana a las 15:00 * Comprar ingredientes para la poción multijugos`\n"
        "Después de apuntarlo, siempre te preguntaré si quieres que te dé un **aviso previo** (ej: `1h`, `30m`).\n\n"
        "📝👀 *VER TUS RECORDATORIOS:*\n"
        "Con /lista podrás ver todos tus recordatorios de forma interactiva. Verás que cada tarea tiene un icono:\n"
        "  - `⬜️`: Esto es algo que tienes **pendiente**.\n"
        "  - `✅`: Esto es algo que ya has marcado como **hecho**. ¡Bien por ti!\n\n"
        "Además, podrás cambiar fácilmente entre la vista de recordatorios pendientes y la de `PASADOS` usando los botones.\n"
        "\n\n⚠️ *IMPORTANTE! ⚠️\n\n🕰️🌍 LA ZONA HORARIA:*\n"
        "Para que te avise a la hora que quieres, es *crucial* que configures bien tu zona horaria en /ajustes. Así me aseguro de que un aviso para las 10 de la mañana te llegue a *tus* 10 de la mañana, y no a las mías.\n\n"
        "-------------------\n"
        "Si quieres ver el listado completo de los comandos disponibles, usa /ayuda en cualquier momento."
    ],
    "onboarding_pide_modo_seguro": [
        "⚙️ Antes de empezar, ayúdame a ajustar la configuración inicial.\n\n"
        "Primero, el *Modo Seguro*. Si lo activas te pediré confirmación antes de borrar o cambiar algo. ¿Eres de los que se lanzan sin pensar o de los que se lo piensan dos veces?"
    ],
    "onboarding_pide_zona_horaria": [
        "👵 Ahora vamos a ajustar tu reloj.\n\n¿Cómo prefieres que encontremos la zona horaria? ¿Con magia o a la antigua usanza?"
    ],
    "onboarding_finalizado": [
        "✅ ¡Excelente! He configurado tu zona horaria a *{timezone}*.\n\n"
        "Todo está listo 👌. Te recomiendo que empieces con /ayuda para ver los comandos disponibles.\n\n"
        "👵 ¡Y no me des muchos disgustos!"
    ],

    # -------------------------------------------------------------------------
    # --- FLujo 2: Comandos Básicos (start, ayuda, lista)
    # -------------------------------------------------------------------------
    "start": [
        "👵 ¡Ay, criatura! Bienvenido de nuevo a tu Recordadora. Usa /ayuda si tu memoria de Doxy 🧚‍♀️ no da para más.",
        "👵 Aquí estoy otra vez… y ya veo que tu memoria es peor que la de mi nieto Neville. ¿Necesitas la /ayuda?",
        "👵 *Ayh… c-cchriatura… shooy La Recooordadora…* (...) \n\n😳 ¡Merlín bendito, que me has pillado sin la dentadura puesta! (/ayuda)."
    ],
    "ayuda_base": [
        "*📖 Comandos de La Recordadora*\n¡Presta atención, no me hagas tener que repetírtelo! \n\n"
        "🙋 /start – Para saludar como es debido.\n"
        "🆘 /ayuda – Para ver esto otra vez, por si acaso.\n"
        "🧙 /info – Para que te vuelva a explicar cómo usar la Recordadora.\n\n"
        "📜 /lista – Para ver y gestionar todos tus recordatorios.\n"
        "⏰ /recordar – Para añadir una nueva tarea a tu lista de desastres.\n"
        "🗑️ /borrar – Para quitar algo que (con suerte) ya has hecho.\n"
        "🔄 /cambiar – Para marcar una tarea como hecha o pendiente.\n"
        "🪄 /editar – Para modificar un recordatorio que ya has creado.\n\n"
        "⚙️ /ajustes – Para personalizar tus manías: modo seguro, tu zona horaria y el resumen mañanero.\n"
        "❌ /cancelar – Para que dejes de hacer lo que estabas haciendo."
    ],
    "ayuda_admin": [
        "\n\n⚠️ /reset – ¡Ni se te ocurra tocar esto si no sabes lo que haces!",
    ],
    "lista_vacia": [
        "📭 ¿No tienes nada pendiente? ¡Increíble! Debes haber usado un giratiempo. O eso, o no estás haciendo suficientes cosas importantes. ¡No te acomodes!",
        "📭 Vaya, ni un solo recordatorio. O eres la persona más organizada del mundo... o la más despistada. Me inclino por lo segundo."
    ],

    # -------------------------------------------------------------------------
    # --- FLujo 3: Creación de Recordatorios (/recordar)
    # -------------------------------------------------------------------------
    "recordar_pide_fecha": [
        "👵📅 Venga, dime qué y para cuándo. Y no tardes. \n\nFormato: `fecha` `*` `texto`\nEj: `Mañana a las 14 * Clases de Herbología`",
    ],
    "recordar_pide_aviso": [
        "⏳ ¿Y cuánto antes quieres que te dé el rapapolvo? ¡Decídete! \n\n(ej: `2h`, `1d`, `30m`, o `0` para ninguno).",
    ],
    "recordatorio_guardado": [
        "📝 ¡Apuntado! *#{id} - {texto} ({fecha})*. Más te vale que lo hagas, criatura.",
        "📝 De acuerdo. *#{id} - {texto} ({fecha})*. A ver si esta vez no se te pasa.",
    ],
    
    # -------------------------------------------------------------------------
    # --- FLujo 4: Edición de Recordatorios (/editar)
    # -------------------------------------------------------------------------
    "editar_elige_opcion": [
        "✅ Perfecto, he encontrado el recordatorio `#{user_id}`: _{texto}_ ({fecha}).\n\n¿Qué quieres cambiarle, criatura?"
    ],
    "editar_pide_recordatorio_nuevo": [
        "✍️ Entendido. El recordatorio actual es:\n`{texto_actual}` ({fecha_actual})\n\nAhora, escríbelo de nuevo con los cambios, usando el formato `fecha` `*` `texto`."
    ],
    "editar_pide_aviso_nuevo": [
        "⏳ De acuerdo. Tu aviso actual está programado para *{aviso_actual}* antes. \n\n¿Cuánto tiempo antes quieres que te avise ahora? (ej: `30m`, `2h`, `0` para ninguno)."
    ],
    "editar_confirmacion_recordatorio": [
        "👍 ¡Hecho! He actualizado el recordatorio `#{user_id}`. Ahora es: _{texto}_ ({fecha})."
    ],
    "editar_confirmacion_aviso": [
        "👍 ¡Listo! He cambiado el aviso para el recordatorio `#{user_id}` a *{aviso_nuevo}* antes."
    ],
    
    # -------------------------------------------------------------------------
    # --- FLujo 5: Ajustes y Configuración (/ajustes)
    # -------------------------------------------------------------------------
    "ajustes_pide_nivel": [
        "👵 A ver, explícame tus manías. ¿Necesitas que te pregunte todo dos veces o eres de los que se lanzan sin pensar?\n\nEl nivel de seguridad actual es *{nivel}*.",
    ],
    "ajustes_confirmados": [
        "✅ Bien, ya está. He guardado tu modo de seguridad en el nivel *{nivel}* (_{descripcion}_). A ver cuánto tardas en arrepentirte.",
    ],
    "niveles_modo_seguro": {
        "0": "Sin confirmaciones", "1": "Confirmar solo al borrar",
        "2": "Confirmar solo al cambiar estado", "3": "Confirmar ambos"
    },
    "timezone_pide_metodo": [
        "👵 De acuerdo, vamos a ajustar tu reloj. Tu zona horaria actual es *{timezone_actual}*.\n\n¿Cómo prefieres que encontremos la nueva? ¿Con magia o a la antigua usanza?"
    ],
    "timezone_pide_ubicacion": ["🪄 ¡Hechizo de localización preparado! Pulsa el botón de abajo para compartir tu ubicación conmigo."],
    "timezone_pide_ciudad": ["✍️ Entendido. Venga, dime el nombre de una ciudad y la buscaré en mis mapas."],
    "timezone_pregunta_confirmacion": ["🤔 ¡Hmph! Según mis mapas, '{ciudad}' está en la zona horaria *{timezone}*. ¿Es correcto? Responde `si` o `no`."],
    "timezone_no_encontrada": ["👵 ¡Criatura! No encuentro esa ciudad en mis mapas. ¿Estás seguro de que la has escrito bien? Inténtalo de nuevo."],
    "timezone_confirmada": ["✅ ¡Entendido! He configurado tu zona horaria a *{timezone}*."],
    "timezone_reintentar": ["De acuerdo. Venga, inténtalo de nuevo. Escríbeme otra ciudad."],
    "timezone_buscando": ["👵 Buscando '{ciudad}' en mi bola de cristal... Dame un segundo."],
    "ajustes_resumen_menu": [
        "🗓️ *Resumen Diario*\n\n"
        "¿Quieres que te dé un rapapolvo mañanero con tus tareas del día? Aquí puedes decidir si te molesto y a qué hora.\n\n"
        "Estado actual: *{estado}*\n"
        "Hora programada: *{hora}*"
    ],

    # -------------------------------------------------------------------------
    # --- FLujo 6: Notificaciones (Avisos y Resumen)
    # -------------------------------------------------------------------------
    "aviso_programado": [
        "🔔 Entendido. Te daré un grito {tiempo} antes. ¡Más te vale estar atento!",
        "🔔 De acuerdo, te avisaré {tiempo} antes. No quiero excusas."
    ],
    "aviso_no_programado": [
        "🤨 ¿Sin aviso? Muy valiente por tu parte. Espero que tu memoria no te falle como a Neville.",
        "🤨 De acuerdo, sin aviso. Allá tú con tu memoria de Doxy."
    ],
    "aviso_principal": [
        "👵⏰ ¡Es la hora de tu deber! Tienes que: *{texto}*",
        "👵⏰ ¡Espabila! Ya es la hora de: *{texto}*. Luego no digas que no te avisé.",
    ],
    "aviso_previo": [
        "👵⚠️ ¡Atención! Dentro de {tiempo} tienes que hacer esto: *{texto}*. ¡Prepárate!",
        "👵⚠️ Que no se te olvide, en {tiempo} te toca: *{texto}*. ¡Ve acabando lo que sea que estés haciendo!",
    ],
    "resumen_diario_con_tareas": [
        "👵 ¡Buenos días, criatura! Más te vale no holgazanear, que para hoy tienes estas tareas:",
        "👵 ¡Arriba, gandul! El sol ya ha salido y estas son tus obligaciones para hoy:",
    ],
    
    # -------------------------------------------------------------------------
    # --- FLujo 7: Operaciones y Confirmaciones
    # -------------------------------------------------------------------------
    "pregunta_confirmar_borrado": ["⚠️ ¿Seguro que quieres borrar {count} recordatorio(s)? Esto no se puede deshacer. Escribe 'SI' para confirmar."],
    "pregunta_confirmar_cambio": ["⚠️ ¿Seguro que quieres cambiar el estado de {count} recordatorio(s)? Escribe 'SI' para confirmar."],
    "confirmacion_borrado": ["🗑️ ¡Borrados los recordatorios con IDs: {ids}!"],
    "confirmacion_cambio": ["🔄 ¡Estado cambiado para los IDs: {ids}!"],
    "aviso_reprogramado": ["✅ ¡Venga, te he vuelto a poner el aviso para `#{id}`! ¡Que no se te pase!"],

    # -------------------------------------------------------------------------
    # --- FLujo 8: Errores y Casos Límite
    # -------------------------------------------------------------------------
    "error_formato": ["❗ ¡Así no, criatura! El formato es `fecha` `*` `texto`. ¡Concéntrate!"],
    "error_no_id": ["⚠️ ¡Desastre! No he encontrado ningún recordatorio tuyo con esos números."],
    "error_aviso_invalido": ["⚠️ ¿Qué formato de tiempo es ese? Usa algo que entienda, como `2h`, `1d` o `30m`."],
    "error_nivel_invalido": ["⚠️ ¡Ese número no vale, criatura! Elige uno del 0 al 3."],
    "error_esperaba_ubicacion": ["👵 ¡Criatura, a ver si me escuchas! Te he pedido que pulses el botón de ubicación."],
    "error_esperaba_ciudad": ["👵 ¡Por las barbas de Merlín! Te he pedido el nombre de una ciudad."],
    "error_geopy": ["👵 ¡Por las barbas de Merlín! Mis mapas mágicos no responden. Inténtalo de nuevo en un momento."],
    "error_interrupcion": ["👵 ¡Quieto ahí, criatura! Estamos en mitad de algo. Si quieres cambiar de tema, usa /cancelar primero."],
    "error_aviso_pasado_reintentar": [
        "👵 ¡Criatura, que no soy una giratiempo! Esa hora para el aviso ya ha pasado.\n\nElige un tiempo que sea en el futuro, o pon `0` si ya no quieres el aviso.",
    ],
    "error_aviso_sin_fecha": [
        "👵 ¿Y cómo quieres que te avise de algo que no tiene fecha? ¡Aclárate primero! No he programado ningún aviso. Pon `0` para continuar sin aviso.",
    ],
    "error_aviso_no_permitido": [
        "👵 ¡Pero qué dices, criatura! No se puede poner un aviso a un recordatorio que ya está hecho o cuya fecha ya ha pasado. ¡Un poco de sentido común!",
        "🤨 ¿Un aviso para algo que ya ha terminado? Venga, elige otra cosa que editar o cancela, que me estás mareando."
    ],

    # -------------------------------------------------------------------------
    # --- FLujo 9: Comandos de Administrador (/reset)
    # -------------------------------------------------------------------------
    "reset_aviso": ["🔥🔥🔥 *¡ATENCIÓN!* 🔥🔥🔥\nEstás a punto de borrarlo *TODO*. Para confirmar, escribe: `CONFIRMAR`"],
    "reset_confirmado": ["🪄✨ ¡Hmph! Hecho. Todo borrado. Espero que sepas lo que has hecho."],
    "reset_cancelado": ["❌ ¡Uff! Operación cancelada. Por un momento pensé que habías perdido la cabeza."],
    "reset_denegado": ["⛔ ¡Quieto ahí! Este es un comando de la abuela. ¡Tú no puedes usarlo!"],

    # -------------------------------------------------------------------------
    # --- FLujo 10: Cancelación Genérica
    # -------------------------------------------------------------------------
    "cancelar": [
        "❌ ¡Hmph! Operación cancelada. Como siempre, dejando las cosas a medias.",
        "❌ De acuerdo, cancelado."
    ],
}

# =============================================================================
# FUNCIÓN DE ACCESO A LOS TEXTOS
# =============================================================================

def get_text(key: str, **kwargs) -> str:
    """
    Obtiene un texto aleatorio de la lista correspondiente a una clave y le da formato.

    Args:
        key (str): La clave del diccionario TEXTOS que se quiere obtener.
        **kwargs: Argumentos dinámicos para formatear el texto (ej: id=123, texto="tarea").

    Returns:
        str: Una de las frases asociadas a la clave, ya formateada.
    """
    # Usamos .get() con un valor por defecto para evitar errores si la clave no existe.
    phrases = TEXTOS.get(key, ["¡Se me ha olvidado qué decir! ¡Esto es culpa tuya, seguro!"])
    
    # Elegimos una frase al azar de la lista de opciones.
    phrase = random.choice(phrases)
    
    # Usamos .format(**kwargs) para reemplazar placeholders como {id} o {texto}.
    return phrase.format(**kwargs)