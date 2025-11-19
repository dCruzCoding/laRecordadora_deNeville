# personality.py
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

TEXTS: Dict[str, List[str]] = {

    # -------------------------------------------------------------------------
    # --- FLujo 1: Bienvenida (Onboarding) y Textos Informativos
    # -------------------------------------------------------------------------
    "onboarding_presentacion": [
        "¡Anda! A buenas horas. A ti te estaba esperando. Ya me dijo mi nieto Neville que le había dejado su recordadora a uno de sus amigos.\n\n"
        "Soy Augusta Longbottom 👵. Bueno, una huella de su personalidad que guardó en esta recordadora para que tratara a su nieto con el _cariño_ que merecía.\n\n" 
        "Mi misión es asegurarme de que no se te olvide nada importante. ¡Y más te vale hacerme caso!"
    ],
    "onboarding_informacion": [
        "*La Recordadora* 🔮 es tu asistente personal mágico. ¡Presta atención a cómo funciono!\n\n"
        
        "➕ *AÑADIR UNA TAREA PUNTUAL*\n"
        "Usa el comando /recordar. Tienes dos formas:\n"
        "  - **Modo Rápido:** Escribe todo de una vez, como `/recordar mañana a las 15:00 * Comprar ingredientes`. ¡Incluso entiendo si solo pones la hora, como `/recordar 18:30 * Pasear al perro`!\n"
        "  - **Modo Interactivo:** Simplemente escribe /recordar y te preguntaré qué tipo de recordatorio quieres crear.\n"
        "Después, siempre te preguntaré si quieres un **aviso previo**.\n\n"

        "📌 *GESTIONAR TAREAS DIARIAS (RECORDATORIOS FIJOS)*\n"
        "Para esas cosas que repites sin parar, usa el comando /fijo. Se abrirá un menú especial donde podrás:\n"
        "  - **Añadir** una nueva tarea recurrente.\n"
        "  - **Editar** o **Borrar** las que ya existen.\n"
        "  - ¡Lo más importante! Podrás **elegir los días de la semana** en que se repite (ej: solo los Lunes y Miércoles).\n\n"

        "📜 *CONSULTAR TUS LISTAS*\n"
        "He separado tus tareas para que todo esté más ordenado:\n"
        "  - **/lista**: Abre tu centro de mandos para las tareas **puntuales**. Desde ahí, podrás filtrar por `Pasados`, `Hechos`, etc.\n"
        "  - **/lista fijos**: Muestra una lista simple y clara de todas tus tareas **recurrentes**.\n\n"

        "🔔 *NOTIFICACIONES INTELIGENTES*\n"
        "Cuando te llegue un aviso, ¡no es solo texto! Tendrá botones para que actúes al momento:\n"
        "  - `✅ Hecho`: Marca la tarea como completada.\n"
        "  - `⏰ +10 min`: Pospone el recordatorio 10 minutos.\n"
        "  - `👌 OK`: Simplemente descarta la notificación.\n\n"

        "🌞 *TU RESUMEN MAÑANERO*\n"
        "Cada mañana a la hora que elijas en /ajustes, te enviaré un resumen con las tareas puntuales que tienes para hoy. ¡No tienes que hacer nada!\n\n"

        "⚠️ *MUY IMPORTANTE: LA ZONA HORARIA*\n"
        "Para que los avisos y el resumen te lleguen a *tu* hora, es crucial que configures bien tu zona horaria en **/ajustes**.\n\n"
        "-------------------\n"
        "Para ver la lista completa de comandos, usa /ayuda en cualquier momento."
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
    # --- Flujo 2: Comandos Básicos (start, ayuda, lista)
    # -------------------------------------------------------------------------
    "start": [
        "👵 ¡Ay, criatura! Bienvenido de nuevo a tu Recordadora. Usa /ayuda si tu memoria de Doxy 🧚‍♀️ no da para más.",
        "👵 Aquí estoy otra vez… y ya veo que tu memoria es peor que la de mi nieto Neville. ¿Necesitas la /ayuda?",
        "👵 *Ayh… c-cchriatura… shooy La Recooordadora…* (...) \n\n😳 ¡Merlín bendito, que me has pillado sin la dentadura puesta! (/ayuda)."
    ],

    "ayuda_base": [

    "*📖 Comandos de La Recordadora*\n"
    "¡Presta atención, no me hagas repetírtelo! \n\n"

    "--- *COMANDOS GENERALES* ---\n"
    "🙋 */start* – Para saludar como es debido. \n"
    "🆘 */ayuda* (o help) – Para ver esto otra vez, por si se te olvida.\n"
    "🧙 */info* (intro) – Para que te vuelva a explicar cómo funciono.\n\n"

    "--- *GESTIÓN DE TAREAS* ---\n"
    "📜 */lista* (list) – Abre tu centro de mandos. ¡Y más te vale usar los filtros!\n"
    "  > `pasados`, `hechos` o `pendientes` para filtrar la vista (ej: `/lista pasados`).\n"
    "  > `fijos` para ver solo los que se repiten (ej: `/lista fijos`).\n\n"
    "⏰ */recordar* – Para añadir una nueva tarea a tu lista de desastres.\n"
    "  > También entiendo: `recordatorio`, `recordatorios`, `add`.\n"
    "  > Tiene modo rápido: \n`/recordar fecha-hora*texto`.\n\n"
    "📌 */fijo* – Abre el menú para gestionar esas tareas que repites sin parar (añadir, editar y borrar).\n"
    "  > También: `fijos`, `recurrente`, `recurrentes`, `pinned`.\n\n"
    "  > Puedes ir directo a la gestión añadiendolo al comando: ej. `/fijos añadir`.\n\n"
    "🗑️ */borrar* – Para quitar algo que (con suerte) ya has hecho.\n"
    "  > También: `delete`, `del`, `bor`.\n"
    "  > Modo rápido: /borrar ID1 ID2 ...\n\n"
    "🔄 */cambiar* – Para marcar una tarea como hecha o pendiente.\n"
    "  > También: `change`, `hecho`, `done`, `check`.\n"
    "  > Modo rápido: /cambiar ID1 ID2 ...\n\n"
    "🪄 */editar* – Para modificar un recordatorio que ya has creado.\n"
    "  > También: `edit`, `modificar`, `mod`.\n"
    "  > Modo rápido: /editar ID1.\n\n"

    "--- *OTROS COMANDOS* ---\n"
    "⚙️ */ajustes* (config) – Para personalizar tus manías: modo seguro, zona horaria y el resumen mañanero.\n"
    "❌ */cancelar* – Para que dejes de hacer lo que estabas haciendo."
    ],


    "ayuda_admin": [
        "\n\n\n *¡OJO! ESTO SÓLO PARA EL ADMIN*"
        "\n\n⚠️ */reset* – ¡Ni se te ocurra tocar esto si no sabes lo que haces!",
    ],
    "lista_vacia": [
        "📭 ¿No tienes nada pendiente? ¡Increíble! Debes haber usado un giratiempo. O eso, o no estás haciendo suficientes cosas importantes. ¡No te acomodes!",
        "📭 Vaya, ni un solo recordatorio. O eres la persona más organizada del mundo... o la más despistada. Me inclino por lo segundo."
    ],

    # -------------------------------------------------------------------------
    # --- Flujo 3: Creación de Recordatorios (/recordar)
    # -------------------------------------------------------------------------
    "recordar_pide_fecha": [
        "👵📅 Venga, dime qué y para cuándo. Y no tardes. \n\nFormato: `fecha` `*` `texto`\nEj: `Mañana a las 14 * Clases de Herbología`",
        "👵📅 A ver, cariño, dime. Aunque visto lo visto, seguro que lo olvidas igual que Neville. \n\nFormato: `fecha * texto`\nEj: `22:07 * Netflix con Luna`."
    ],
    "recordar_pide_aviso": [
        "⏳ ¿Y cuánto antes quieres que te dé el rapapolvo? ¡Decídete! \n\n(ej: `2h`, `1d`, `30m`, o `0` para ninguno).",
        "⏳ ¿Te aviso un poco antes? Mejor prevenir que necesitar un giratiempo. \n\n*(ej: 2h, 1d, 30m, 0 para ninguno)*."
    ],
    "recordatorio_guardado": [
        "📝 ¡Apuntado! *#{id} - {text} ({date})*. Más te vale que lo hagas, criatura.",
        "📝 De acuerdo. *#{id} - {text} ({date})*. A ver si esta vez no se te pasa.",
        "📝 Registrado. *#{id} - {text} ({date})*. No me hagas ir a buscarte.",
        "📝 Listo. *#{id} - {text} ({date})*. ¿Por fín apuntas ir a visitar a tu abuela?.",
        "Dios mío que pesadilla, ¿por qué le prometería a mi nieto que te ayudaría? \n\n📝 *#{id} - {text} ({date})*.",
        "¡Ay! Qué me has pillado en el baño. Espera que voy a apuntarlo. (...) \n\n📝 Vale, ya. *#{id} - {text} ({date})*."
    ],
    
    # -------------------------------------------------------------------------
    # --- Flujo 4: Edición de Recordatorios (/editar)
    # -------------------------------------------------------------------------
    "editar_elige_opcion": [
        "✅ Perfecto, he encontrado el recordatorio `#{user_id}`: _{text}_ ({date}).\n\n¿Qué quieres cambiarle, criatura?"
    ],
    "editar_pide_recordatorio_nuevo": [
        "✍️ Entendido. El recordatorio actual es:\n`{current_text}` ({current_date})\n\nAhora, escríbelo de nuevo con los cambios, usando el formato `fecha` `*` `texto`."
    ],
    "editar_pide_aviso_nuevo": [
        "⏳ De acuerdo. Tu aviso actual está programado para *{current_alert}* antes. \n\n¿Cuánto tiempo antes quieres que te avise ahora? (ej: `30m`, `2h`, `0` para ninguno)."
    ],
    "editar_confirmacion_recordatorio": [
        "👍 ¡Hecho! He actualizado el recordatorio `#{user_id}`. Ahora es: _{text}_ ({date})."
    ],
    "editar_confirmacion_aviso": [
        "👍 ¡Listo! He cambiado el aviso para el recordatorio `#{user_id}` a *{new_alert}* antes."
    ],
    
    # -------------------------------------------------------------------------
    # --- Flujo 5: Ajustes y Configuración (/ajustes)
    # -------------------------------------------------------------------------
    "ajustes_pide_nivel": [
        "👵 A ver, explícame tus manías. ¿Necesitas que te pregunte todo dos veces o eres de los que se lanzan sin pensar?\n\nEl nivel de seguridad actual es *{level}*.",
        "👵 ¿Quieres que te trate con guantes de seda o que confíe en que no vas a romper nada?. Nivel actual: *{level}*."
    ],
    "ajustes_confirmados": [
        "✅ Bien, ya está. He guardado tu modo de seguridad en el nivel *{level}* (_{description}_). A ver cuánto tardas en arrepentirte.",
        "✨ Perfecto, criatura. La configuración ha quedado fijada en nivel *{level}* (_{description}_), por arte de magia."
    ],
    "niveles_modo_seguro": {
        "0": "Sin confirmaciones", "1": "Confirmar solo al borrar",
        "2": "Confirmar solo al cambiar estado", "3": "Confirmar ambos"
    },
    "timezone_pide_metodo": [
        "👵 De acuerdo, vamos a ajustar tu reloj. Tu zona horaria actual es *{current_timezone}*.\n\n¿Cómo prefieres que encontremos la nueva? ¿Con magia o a la antigua usanza?"
    ],
    "timezone_pide_ubicacion": ["🪄 ¡Hechizo de localización preparado! Pulsa el botón de abajo para compartir tu ubicación conmigo."],
    "timezone_pide_ciudad": ["✍️ Entendido. Venga, dime el nombre de una ciudad y la buscaré en mis mapas."],
    "timezone_pregunta_confirmacion": ["🤔 ¡Hmph! Según mis mapas, '{city}' está en la zona horaria *{timezone}*. ¿Es correcto? Responde `si` o `no`."],
    "timezone_no_encontrada": ["👵 ¡Criatura! No encuentro esa ciudad en mis mapas. ¿Estás seguro de que la has escrito bien? Inténtalo de nuevo."],
    "timezone_confirmada": ["✅ ¡Entendido! He configurado tu zona horaria a *{timezone}*."],
    "timezone_reintentar": ["De acuerdo. Venga, inténtalo de nuevo. Escríbeme otra ciudad."],
    "timezone_buscando": ["👵 Buscando '{city}' en mi bola de cristal... Dame un segundo.",
                "👵 A ver dónde queda esa ciudad de '{city}'... Un momento, estoy consultando mis mapas mágicos."],
    "ajustes_resumen_menu": [
        "🗓️ *Resumen Diario*\n\n"
        "¿Quieres que te dé un rapapolvo mañanero con tus tareas del día? Aquí puedes decidir si te molesto y a qué hora.\n\n"
        "Estado actual: *{status}*\n"
        "Hora programada: *{hour}*"
    ],

    # -------------------------------------------------------------------------
    # --- Flujo 6: Notificaciones (Avisos y Resumen)
    # -------------------------------------------------------------------------
    "aviso_programado": [
        "🔔 Entendido. Te daré un grito {time} antes. ¡Más te vale estar atento!",
        "🔔 De acuerdo, te avisaré {time} antes. No quiero excusas.",
        "🔔 Perfecto, {time} antes me oirás. Y no será para darte las buenas noches."
    ],
    "aviso_no_programado": [
        "🤨 ¿Sin aviso? Muy valiente por tu parte. Espero que tu memoria no te falle como a Neville.",
        "🤨 De acuerdo, sin aviso. Allá tú con tu memoria de Doxy."
    ],
    "aviso_principal": [
        "👵⏰ ¡Es la hora de tu deber! Tienes que: *{text}*",
        "👵⏰ ¡Espabila! Ya es la hora de: *{text}*. Luego no digas que no te avisé.",
        "👵⏰ ¡GRYFFINDOR! ¡Es la hora de tu deber! Tienes que: *{text}*. ¡Haz que esta abuela se sienta orgullosa!"
    ],
    "aviso_previo": [
        "👵⚠️ ¡Atención! Dentro de {time} tienes que hacer esto: *{text}*. ¡Prepárate!",
        "👵⚠️ Que no se te olvide, en {time} te toca: *{text}*. ¡Ve acabando lo que sea que estés haciendo!",
        "👵⚠️ Te aviso con tiempo para que no tengas excusas. En {time}: '{text}'.",
        "👵⚠️ Dentro de {time} tienes esto: '{text}'. Y llama a tu abuela que la tienes abandonada."
    ],
    "resumen_diario_con_tareas": [
        "👵 ¡Buenos días, criatura! Más te vale no holgazanear, que para hoy tienes estas tareas:",
        "👵 ¡Arriba, gandul/a! El sol ya ha salido y estas son tus obligaciones para hoy:",
    ],
    
    # -------------------------------------------------------------------------
    # --- Flujo 7: Operaciones y Confirmaciones
    # -------------------------------------------------------------------------
    "pregunta_confirmar_borrado": ["⚠️ ¿Seguro que quieres borrar {count} recordatorio(s)? Esto no se puede deshacer. Escribe 'SI' para confirmar.",
                    "⚠️ A ver, criatura, que te conozco. ¿Seguro que quieres borrar {count} cosa(s)? Luego vienen los lloros. Escribe 'SI' para confirmar."],
    "pregunta_confirmar_cambio": ["⚠️ ¿Seguro que quieres cambiar el estado de {count} recordatorio(s)? Escribe 'SI' para confirmar.",
                    "⚠️ ¿Seguro que quieres cambiar el estado de {count} recordatorio(s)? A ver si lo vas a cambiar otra vez en cinco minutos... Escribe 'SI' para confirmar."],
    "confirmacion_borrado": ["🗑️ ¡Borrados los recordatorios con IDs: {ids}!",
                        "🗑️ ¡Wingardium Leviosa y a la basura! Los recordatorios {ids}, fuera de la lista."],
    "confirmacion_cambio": ["🔄 ¡Estado cambiado para los IDs: {ids}!",
        "🔄 ¡Cambiado! Pero... ¿estás seguro que querías hacer eso? (IDs: {ids})",
        "🔄 Cambiado. Vaya, vaya… ¡si hasta pareces más organizado que Neville por un segundo!",
        "🔄 Vale ya cambié lo que me dijiste. ¿Eran los recordatorios 94 y 95 no? Jeje es broma, éstos son los IDs: {ids}."],
    "aviso_reprogramado": ["✅ ¡Venga, te he vuelto a poner el aviso para `#{id}`! ¡Que no se te pase!"],

    # -------------------------------------------------------------------------
    # --- Flujo 8: Errores y Casos Límite
    # -------------------------------------------------------------------------
    "error_formato": [
        "❗ ¡Así no, criatura! El formato es `fecha * texto`. ¡Concéntrate!",
        "❗ ¿Pero qué escribes? Tiene que ser `fecha * texto`. A veces pienso que te criaron los gnomos de jardín.",
        "❗ Te has equivocado con el formato del recordatorio: `fecha * texto`. \n\nNo te preocupes, mi Neville que tanto se equivocaba llegó a ser una persona y mago maravilloso. \n\n ¿Te ha hablado de cuando derrotó al Señor Tenebroso? ¿No? Pues verás en la gran batalla de Hogwarts la mismísima espada de Griffindor se le apareció y... \n\n Ay bueno, que me lío. Quiero decir que si mi nieto pudo, tu también podrás.",
        "❗ Te has equivocado con el formato del recordatorio: `fecha * texto`. \n\nNo te preocupes, mi Neville que tanto se equivocaba llegó a ser una persona y mago maravilloso. \n\n ¿Te ha hablado de cuando derrotó al Señor Tenebroso? ¿No? Bueno, pues ahora no puedo."
    ],
    "error_no_id": ["⚠️ ¡Desastre! No he encontrado ningún recordatorio tuyo con esos números.",
        "⚠️ ¿Estás seguro de ese número? Porque yo no veo nada.",
        "⚠️ ¿Tengo que volver a decirte que hasta Neville lo hacía mejor? Porque hasta Neville lo hacía mejor."],
    "error_aviso_invalido": ["⚠️ ¿Qué formato de tiempo es ese? Usa algo que entienda, como `2h`, `1d` o `30m`.",
            "⚠️ Ese tiempo de aviso no vale. Pon `2h`, `1d`, `30m` o `0`. ¡Parece que estás hablando pársel!"],
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
    # --- Flujo 9: Comandos de Administrador (/reset)
    # -------------------------------------------------------------------------
    "reset_aviso": ["🔥🔥🔥 *¡ATENCIÓN!* 🔥🔥🔥\nEstás a punto de borrarlo *TODO*. Para confirmar, escribe: `CONFIRMAR`",
                        "🔥 Ay, ay… esto es lo que haría Neville cuando no entiende un hechizo. No lo hagas si no sabes lo que tocas."],
    "reset_confirmado": ["🪄✨ ¡Hmph! Hecho. Todo borrado. Espero que sepas lo que has hecho.",
                         "🪄✨ 🧹¡Fregotego! Ala, a juí."],
    "reset_cancelado": ["❌ ¡Uff! Operación cancelada. Por un momento pensé que habías perdido la cabeza.",
                    "❌ Cancelado. Menos mal… otro susto como este y acabo comparándote con Neville otra vez."],
    "reset_denegado": ["⛔ ¡Quieto ahí! Este es un comando de la abuela. ¡Tú no puedes usarlo!"],

    # -------------------------------------------------------------------------
    # --- Flujo 10: Cancelación Genérica
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
    phrases = TEXTS.get(key, ["¡Se me ha olvidado qué decir! ¡Esto es culpa tuya, seguro!"])
    
    # Elegimos una frase al azar de la lista de opciones.
    phrase = random.choice(phrases)
    
    # Usamos .format(**kwargs) para reemplazar placeholders como {id} o {texto}.
    return phrase.format(**kwargs)