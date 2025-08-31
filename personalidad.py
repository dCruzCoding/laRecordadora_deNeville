import random

TEXTOS = {
    # --- Flujo de Bienvenida (Onboarding) ---
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
        "Con /lista podrás ver todos tus recordatorios. Verás que cada tarea tiene un icono:\n"
        "  - `⬜️`: Esto es algo que tienes **pendiente**.\n"
        "  - `✅`: Esto es algo que ya has marcado como **hecho**. ¡Bien por ti! El texto aparecerá tachado.\n\n"
        "Además, aquellos recordatorios que ya han pasado aparecerán en una sección aparte denominada `PASADOS`, a los cuales no podrás añadir avisos pero sí marcarlos como hechos o pendientes.\n"

        "\n\n⚠️ *IMPORTANTE! ⚠️\n\n🕰️🌍 LA ZONA HORARIA:*\n"
        "Para que te avise a la hora que quieres, es *crucial* que configures bien tu zona horaria. Así me aseguro de que un aviso para las 10 de la mañana te llegue a *tus* 10 de la mañana, y no a las mías.\n\n"
        "Por ello, ten en cuenta que *si viajas a otra zona horaria, deberás actualizar tu configuración y tus recordatorios*.\n\n"
        "-------------------\n"
        "Si quieres ver el listado completo de los comandos disponibles, usa /ayuda en cualquier momento."
    ],
    "onboarding_pide_modo_seguro": [
        "⚙️ Antes de empezar, ayúdame a ajustar la configuración inicial.\n\n"
        "Primero, el *Modo Seguro*. Si lo activas te pediré confirmación antes de borrar o cambiar algo. ¿Eres de los que se lanzan sin pensar o de los que se lo piensan dos veces?\n\n"
        "Tu nivel actual es: *{nivel}*\n\n"
        "Elige un nuevo nivel (0-3):\n"
        "  *0* → 🔓 *Sin confirmaciones*.\n"
        "  *1* → 🗑 Confirmar solo al *borrar*.\n"
        "  *2* → 🔄 Confirmar solo al *cambiar estado*.\n"
        "  *3* → 🔒 Confirmar *ambos*."
    ],
    "onboarding_pide_zona_horaria": [
        "👵 Ahora vamos a ajustar tu reloj.\n\n¿Cómo prefieres que encontremos la zona horaria? ¿Con magia o a la antigua usanza?"
    ],
    "onboarding_finalizado": [
        "✅ ¡Excelente! He configurado tu zona horaria a *{timezone}*.\n\n"
        "Todo está listo 👌. Te recomiendo que empieces con /ayuda para ver los comandos disponibles.\n\n"
        "👵 ¡Y no me des muchos disgustos!"
    ],

    # --- Comandos Básicos ---

    "start": [
        "👵 ¡Ay, criatura! Bienvenido a tu Recordadora. \n\nA ver qué desastre se te ha olvidado esta vez. Usa /ayuda si tu memoria de Doxy 🧚‍♀️ no da para más.",
        "👵 Aquí estoy otra vez… y ya veo que tu memoria es peor que la de mi nieto Neville. \n\nY créeme, eso ya es decir mucho. ¿Necesitas la /ayuda?",
        "👵 *Ayh… c-cchriatura… shooy La Recooordadora…* (...) \n\n😳 ¡Merlín bendito, que me has pillado sin la dentadura puesta! (/ayuda)."
    ],
    "ayuda_base": [
        "*📖 Comandos de La Recordadora*\n¡Presta atención, no me hagas tener que repetírtelo! \n\n"
        "🙋 /start – Para saludar como es debido.\n"
        "\n🆘 /ayuda – Para ver esto otra vez, por si acaso.\n"
        "🧙 /info – Para que te vuelva a explicar cómo usar la Recordadora.\n"
        "\n📜 /lista – Te enseñaré lo que tienes pendiente, ¡a ver si te pones al día!\n"
        "⏰ /recordar – Para añadir una nueva tarea a tu lista de desastres.\n"
        "🗑️ /borrar – Para quitar algo que (con suerte) ya has hecho.\n"
        "🔄 /cambiar – Cuando por fín logres terminar algo, o cuando luego veas que te confundiste y todavía no lo acabaste.\n"
        "🪄 /editar – Para modificar un recordatorio que ya has creado (o su aviso).\n"
        "\n⚙️ /ajustes – Para personalizar tus manías: modo seguro, tu zona horaria y si quieres (y a qué hora) mi resumen mañanero.\n"
        "\n❌ /cancelar – Para que dejes de hacer lo que estabas haciendo."
    ],
    "ayuda_admin": [
        "\n\n⚠️ /reset – ¡Ni se te ocurra tocar esto si no sabes lo que haces!",
        "\n\n⚠️ ¿/reset dices? Ay, igualito que Neville toqueteando lo que no entiende."
    ],
        "lista_vacia": [
        "📭 ¿No tienes nada pendiente? ¡Increíble! Debes haber usado un giratiempo. O eso, o no estás haciendo suficientes cosas importantes. ¡No te acomodes!",
        "📭 Vaya, ni un solo recordatorio. O eres la persona más organizada del mundo... o la más despistada. Me inclino por lo segundo."
    ],

    # --- Flujo de Recordar ---
    "recordar_pide_fecha": [
        "👵📅 Venga, dime qué y para cuándo. Y no tardes. \n\nFormato: `fecha` `*` `texto`. En la fecha es obligatorio que me digas el día, la hora ya es opcional.\n\nEj: Mañana a las 14`*`Clases de Herbología",
        "👵📅 A ver, cariño, dime qué y para cuándo… aunque visto lo visto, seguro que lo olvidas igual que Neville. \n\nFormato: `fecha` `*` `texto` (fecha: dia obligatorio hora opcional).\n\nEj: 20 Julio`*`Entrega proyecto Encantamientos"
    ],
    "recordar_pide_aviso": [
        "⏳ ¿Y cuánto antes quieres que te dé el rapapolvo? ¡Decídete! \n\n*(ej: 2h, 1d, 30m, 0 para ninguno)*.",
        "⏳ Dime cuánto tiempo antes quieres que te avise, mejor prevenir que necesitar un giratiempo. \n\n*(ej: 2h, 1d, 30m, 0 para ninguno)*."
    ],
    "recordatorio_guardado": [
        "📝 ¡Apuntado! *#{id} - {texto} ({fecha})*. Más te vale que lo hagas, criatura.",
        "📝 De acuerdo. *#{id} - {texto} ({fecha})*. A ver si esta vez no se te pasa.",
        "📝 Registrado. *#{id} - {texto} ({fecha})*. No me hagas ir a buscarte.",
        "📝 Listo. *#{id} - {texto} ({fecha})*. ¿Por fín apuntas ir a visitar a tu abuela?.",
        "Dios mío que pesadilla, ¿por qué le prometería a mi nieto que te ayudaría? \n\n📝 *#{id} - {texto} ({fecha})*.",
        "¡Ay! Qué me has pillado en el baño. Espera que voy a apuntarlo. (...) \n\n📝 Vale, ya. *#{id} - {texto} ({fecha})*."
    ],
    "recordatorio_pasado_lista": [
        "👵🗂️ ¡Esto ya se te ha pasado! Más te vale que lo hayas hecho aunque no te lo haya recordado a tiempo.",
        "👵🗂️ Se te pasó el arroz con esto. A ver si prestamos más atención al calendario."
    ],

    # --- Flujo de Editar ---
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

    # --- Ajustes ---
    "ajustes_pide_nivel": [
        "👵 A ver, explícame tus manías. ¿Necesitas que te pregunte todo dos veces o eres de los que se lanzan sin pensar?\n\nEl nivel actual es *{nivel}*.",
        "👵 ¿Quieres que te trate con guantes de seda o que confíe en que no vas a romper nada?. Nivel actual: *{nivel}*."
    ],
    "pregunta_confirmar_borrado": [
        "⚠️ ¿Estás completamente seguro de que quieres borrar {count} recordatorio(s)? Esto no se puede deshacer. Escribe 'SI' si no te tiembla el pulso.",
        "⚠️ ¡Quieto ahí! Vas a borrar {count} cosa(s). ¿Estás seguro? Responde 'SI' si es que sí.",
        "⚠️ A ver, criatura, que te conozco. ¿Seguro que quieres borrar {count} cosa(s)? Luego vienen los lloros. Escribe 'SI' para confirmar."
    ],
    "pregunta_confirmar_cambio": [
        "⚠️ ¿Seguro que quieres cambiar el estado de {count} recordatorio(s)? A ver si lo vas a cambiar otra vez en cinco minutos... Escribe 'SI' para confirmar.",
        "⚠️ Vas a cambiar {count} tarea(s). ¿Lo has pensado bien? Escribe 'SI' si estás seguro."
    ],
    "ajustes_confirmados": [
        "✅ Bien, ya está. He guardado tu modo de seguridad en el nivel *{nivel}* (_{descripcion}_). A ver cuánto tardas en arrepentirte.",
        "✨ Perfecto, criatura. La configuración ha quedado fijada en nivel *{nivel}* (_{descripcion}_), por arte de magia."
    ],
    "niveles_modo_seguro": {
        "0": "Sin confirmaciones",
        "1": "Confirmar solo al borrar",
        "2": "Confirmar solo al cambiar estado",
        "3": "Confirmar ambos"
    },
    "timezone_pide_metodo": [
        "👵 De acuerdo, vamos a ajustar tu reloj. Tu zona horaria actual es *{timezone_actual}*.\n\n¿Cómo prefieres que encontremos la nueva? ¿Con magia o a la antigua usanza?"
    ],
    "timezone_pide_ubicacion": [
        "🪄 ¡Hechizo de localización preparado! Ahora solo tienes que pulsar el botón de abajo para compartir tu ubicación conmigo."
    ],
    "timezone_pide_ciudad": [
        "✍️ Entendido. Venga, dime el nombre de una ciudad y la buscaré en mi bola de cristal (o en mis mapas, lo que pille más a mano)."
    ],
    "timezone_pregunta_confirmacion": [
        "🤔 ¡Hmph! Según mis mapas, la ciudad '{ciudad}' está en la zona horaria *{timezone}*. ¿Es correcto? Responde `si` o `no`."
    ],
    "timezone_no_encontrada": [
        "👵 ¡Criatura! No encuentro esa ciudad en ninguno de mis mapas. ¿Estás seguro de que la has escrito bien? Inténtalo de nuevo, y pon las tildes si las lleva."
    ],
    "timezone_confirmada": [
        "✅ ¡Entendido! He configurado tu zona horaria a *{timezone}*. A partir de ahora, todo funcionará según tu hora local."
    ],
    "timezone_reintentar": [
        "De acuerdo. Venga, inténtalo de nuevo. Escríbeme otra ciudad."
    ],
    "timezone_buscando": [
        "👵 Buscando '{ciudad}' en mi bola de cristal... Dame un segundo, que ya no tengo la vista que tenía.",
        "👵 A ver dónde para esa ciudad de '{ciudad}'... Un momento, estoy consultando mis mapas mágicos.",
    ],
    "ajustes_resumen_menu": [
        "🗓️ *Resumen Diario*\n\n"
        "¿Quieres que te dé un rapapolvo mañanero con tus tareas del día? Aquí puedes decidir si te molesto y a qué hora.\n\n"
        "Estado actual: *{estado}*\n"
        "Hora programada: *{hora}*"
    ],

    # --- Avisos ---
    "aviso_programado": [
        "🔔 Entendido. Te daré un grito {tiempo} antes. ¡Más te vale estar atento!",
        "🔔 De acuerdo, te avisaré {tiempo} antes. No quiero excusas.",
        "🔔 ¡Perfecto! {tiempo} antes me oirás. Y no será para darte las buenas noches."
    ],
    "aviso_no_programado": [
        "🤨 ¿Sin aviso? Muy valiente por tu parte. Espero que tu memoria no te falle como a Neville.",
        "🤨 De acuerdo, sin aviso. Allá tú con tu memoria de Doxy."
    ],
    "aviso_principal": [
        "👵⏰ ¡GRYFFINDOR! ¡Es la hora de tu deber! Tienes que: '{texto}'. ¡Haz que esta abuela se sienta orgullosa!",
        "👵⏰ ¡Espabila! Ya es la hora de: '{texto}'. Luego no digas que no te avisé.",
        "👵⏰ ¡Vamos, vamos, vamos! Tienes que hacer esto ahora: '{texto}'. ¡No querrás que la abuela se enfade!"
    ],
    "aviso_previo": [
        "👵⚠️ ¡Atención! Dentro de {tiempo} tienes que hacer esto: '{texto}'. ¡Prepárate!",
        "👵⚠️ Que no se te olvide, en {tiempo} te toca: '{texto}'. ¡Ve acabando lo que sea que estés haciendo!",
        "👵⚠️ Te aviso con tiempo para que no tengas excusas. En {tiempo}: '{texto}'.",
        "👵⚠️ Dentro de {tiempo} tienes esto: '{texto}'. Y llama a tu abuela que la tienes abandonada."
    ],

    # --- Operaciones (Borrar, Cambiar) ---
    "confirmacion_borrado": [
        "🗑️ ¡Borrados los recordatorios con IDs: {ids}!",
        "🗑️ ¡Wingardium Leviosa y a la basura! Los recordatorios {ids}, fuera de la lista."
    ],
    "confirmacion_cambio": [
        "🔄 ¡Cambiado! Pero... ¿estás seguro que querías hacer eso? (IDs: {ids})",
        "🔄 Cambiado. Vaya, vaya… ¡si hasta pareces más organizado que Neville por un segundo!",
        "🔄 Vale ya cambié lo que me dijiste. ¿Eran los recordatorios 94 y 95 no? Jeje es broma, éstos son los IDs: {ids}.",
    ],
    "aviso_reprogramado": [
        "✅ ¡Venga, te he vuelto a poner el aviso para `#{id}`! ¡Que no se te pase!"
    ],

    # --- Resumen Diario ---
    "resumen_diario_con_tareas": [
        "👵 ¡Buenos días, criatura! Más te vale no holgazanear, que para hoy tienes estas tareas:",
        "👵 ¡Arriba, gandul! El sol ya ha salido y estas son tus obligaciones para hoy:",
        "👵 Venga, a levantarse. Te he preparado el desayuno y la lista de tus quehaceres de hoy. No me decepciones."
    ],

    # --- Errores ---
    "error_formato": [
        "❗ ¡Así no, criatura! El formato es `fecha` `*` `texto`. ¡Concéntrate!",
        "❗ ¿Pero qué escribes? Tiene que ser `fecha` `*` `texto`. A veces pienso que te criaron los gnomos de jardín.",
        "❗ Te has equivocado con el formato del recordatorio: `fecha` `*` `texto`. \n\nNo te preocupes, mi Neville que tanto se equivocaba llegó a ser una persona y mago maravilloso. \n\n ¿Te ha hablado de cuando derrotó al Señor Tenebroso? ¿No? Pues verás en la gran batalla de Hogwarts la mismísima espada de Griffindor se le apareció y... \n\n Ay bueno, que me lío. Quiero decir que si mi nieto pudo, tu también podrás.",
        "❗ Te has equivocado con el formato del recordatorio: `fecha` `*` `texto`. \n\nNo te preocupes, mi Neville que tanto se equivocaba llegó a ser una persona y mago maravilloso. \n\n ¿Te ha hablado de cuando derrotó al Señor Tenebroso? ¿No? Bueno, pues ahora no puedo."
    ],
    "error_no_id": [
        "⚠️ ¡Desastre! No he encontrado ningún recordatorio tuyo con esos números.",
        "⚠️ ¿Estás seguro de ese número? Porque yo no veo nada.",
        "⚠️ ¿Tengo que volver a decirte que hasta Neville lo hacía mejor? Porque hasta Neville lo hacía mejor.",
        "⚠️ En algo te equivocaste con el ID del recordatorio. No te preocupes, mi Neville que tanto se equivocaba llegó a ser una persona y mago maravilloso. ¿Te ha hablado de cuando derrotó al Señor Tenebroso? ¿No? Pues verás en la gran batalla de Hogwarts la mismísima espada de Griffindor se le apareció para que la blandiera y... Ay bueno, que me lío. Quiero decir que si mi nieto pudo, tu también podrás.",
        "⚠️ Te has equivocado con el ID del recordatorio. No te preocupes, mi Neville que tanto se equivocaba llegó a ser una persona y mago maravilloso. ¿Te ha hablado de cuando derrotó al Señor Tenebroso? ¿No? Bueno, pues ahora no puedo."
    ],
    "error_aviso_invalido": [
        "⚠️ ¿Qué formato de tiempo es ese? Usa algo que entienda, como `2h`, `1d` o `30m`. ¡No me hagas sacar la lechuza!",
        "⚠️ Ese tiempo de aviso no vale. Pon `2h`, `1d`, `30m` o `0`. ¡Parece que estás hablando pársel!"
    ],
    "error_nivel_invalido": [
        "⚠️ ¡Ese número no vale, criatura! Elige uno del 0 al 3.",
        "⚠️ ¿Qué parte de 'un número del 0 al 3' no has entendido? ¡Venga, otra vez!"
    ],
    "error_esperaba_ubicacion": [
        "👵 ¡Criatura, a ver si me escuchas! Te he pedido que pulses el botón para compartir tu ubicación, no que me escribas la biblia en verso. ¡Inténtalo de nuevo!"
    ],
    "error_esperaba_ciudad": [
        "👵 ¡Por las barbas de Merlín! Te he pedido que me escribas el nombre de una ciudad. ¿Qué es eso de enviarme un mapa? ¡Venga, escribe!"
    ],
    "error_geopy": [
        "👵 ¡Por las barbas de Merlín! Mis mapas mágicos no responden. Parece que hay interferencia en la red. Inténtalo de nuevo en un momento.",
        "👵 ¡Ay, criatura! No consigo conectar con mis fuentes. La magia de la localización está fallando. Prueba a escribir la ciudad otra vez en unos minutos."
    ],
    "error_interrupcion": [
        "👵 ¡Quieto ahí, criatura! Estamos en mitad de algo. Si te gusta dejar las cosas a medias, primero escribe /cancelar y luego ya me mareas con otra cosa.",
        "👵 ¿Ya te has distraído? ¡Termina lo que has empezado! O si de verdad quieres cambiar de tema, usa /cancelar primero."
    ],

    # --- Flujo de Reset ---
    "reset_aviso": [
        "🔥🔥🔥 *¡ATENCIÓN, CRIATURA!* 🔥🔥🔥\n\n"
        "Estás a punto de borrarlo *TODO*. Absolutamente todo. No habrá vuelta atrás. "
        "Si estás completamente seguro, escribe: `CONFIRMAR`",
        "🔥 Ay, ay… esto es lo que haría Neville cuando no entiende un hechizo. No lo hagas si no sabes lo que tocas."
    ],
    "reset_confirmado": [
        "🪄✨ ¡Hmph! Hecho. Todo borrado. Espero que sepas lo que has hecho.",
        "🪄✨ 🧹¡Fregotego! Ala, a juí."
    ],
    "reset_cancelado": [
        "❌ ¡Uff! Operación cancelada. Por un momento pensé que habías perdido la cabeza.",
        "❌ Cancelado. Menos mal… otro susto como este y acabo comparándote con Neville otra vez."
    ],
    "reset_denegado": [
        "⛔ ¡Quieto ahí! Este es un comando de la abuela. ¡Tú no puedes usarlo!"
    ],

    # --- Cancelación Genérica ---
    "cancelar": [
        "❌ ¡Hmph! Operación cancelada. Como siempre, dejando las cosas a medias.",
        "❌ Cancelado. Espero que sepas lo que haces."
    ],
}

def get_text(key: str, **kwargs) -> str:
    """
    Obtiene un texto aleatorio de la lista correspondiente y le da formato.
    """
    # Obtenemos la lista de frases, con un mensaje de error por defecto
    phrases = TEXTOS.get(key, ["¡Se me ha olvidado qué decir! ¡Esto es culpa tuya, seguro!"])
    
    # Elegimos una frase al azar
    phrase = random.choice(phrases)
    
    # Le aplicamos el formato con los argumentos que nos pasen
    return phrase.format(**kwargs)