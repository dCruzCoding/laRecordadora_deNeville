import random

TEXTOS = {
    # --- Comando inicial ---

    "start_inicio": [
        "¡Anda! A buenas horas. A tí te estaba esperando. Ya me dijo Neville que le había dejado su recordadora a unos cuántos amigos. \n"
        "\nEncantada de conocerte, soy Augusta Longbottom, la abuela de Neville 👵. \n"
        "\nBueno, realmente soy una huella de su personalidad que guardó en esta recordadora para que tratara a su nieto con el _cariño_ que merecía. \n"
        "\nTe explico como funciona *La Recordadora*: es una 🪄herramienta mágica🪄 que *te ayudará a recordar tus tareas y compromisos*. Solo tienes que decirme qué necesitas y cuándo. \n"
        "\n‼🔮 Con /ayuda te muestro la lista de cosas que podemos hacer. Así que venga, manos a la obra."
    ],

    # --- Comandos Básicos ---

    "start": [
        "👵 ¡Ay, criatura! Soy 🔮*La Recordadora*✨. A ver qué desastre se te ha olvidado esta vez. Usa /ayuda si tu memoria de Doxy 🧚‍♀️ no da para más.",
        "👵 Aquí estoy otra vez… y ya veo que tu memoria es peor que la de mi nieto Neville. Y créeme, eso ya es decir mucho. ¿Necesitas la /ayuda?",
        "👵 *Ayh… c-cchriatura… shooy La Recooordadora…* (...) 😳 ¡Merlín bendito, que me habéis pillado sin la dentadura puesta! (/ayuda)."
    ],
    "ayuda_base": [
        "*📖 Órdenes de La Recordadora*\n\n¡Presta atención, que no lo repetiré dos veces! 👵\n\n"
        "📌 /start – Lo primero es saludar como es debido.\n"
        "📌 /ayuda – Para ver esto otra vez, por si acaso.\n"
        "📌 /lista – Te enseñaré lo que tienes pendiente, ¡a ver si te pones al día!\n"
        "\n📌 /recordar – Para añadir una nueva tarea a tu lista de desastres.\n"
        "📌 /borrar – Para quitar algo que (con suerte) ya has hecho.\n"
        "📌 /cambiar – Cuando por fín logres terminar algo, o cuando luego veas que te confundiste y todavía no lo acabaste.\n"
        "\n📌 /configuracion – Para ajustar tus manías con las confirmaciones de borrado o cambio de estado.\n"
        "📌 /cancelar – Para que dejes de hacer lo que estabas haciendo."
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
        "👵📅 Venga, dime qué y para cuándo. Y no tardes. Formato: `fecha * texto`.",
        "👵📅 A ver, cariño, dime qué y para cuándo… aunque visto lo visto, seguro que lo olvidas igual que Neville (formato: `fecha * texto`)."
    ],
    "recordar_pide_aviso": [
        "⏳ ¿Y cuánto antes quieres que te dé el rapapolvo? *(ej: `2h`, `1d`, `30m`, `0` para ninguno)*. ¡Decídete!",
        "⏳ Dime cuánto tiempo antes quieres que te avise, mejor prevenir que necesitar un giratiempo *(ej: `2h`, `1d`, `30m`, `0` para ninguno)*."
    ],
    "recordatorio_guardado": [
        "📝 ¡Apuntado! *`#{id}` - {texto} ({fecha})*. Más te vale que lo hagas, criatura.",
        "📝 De acuerdo. *`#{id}` - {texto} ({fecha})*. A ver si esta vez no se te pasa.",
        "📝 Registrado. *`#{id}` - {texto} ({fecha})*. No me hagas ir a buscarte.",
        "📝 Listo. *`#{id}` - {texto} ({fecha})*. ¿Por fín apuntas ir a visitar a tu abuela?.",
        "Dios mío que pesadilla, ¿por qué le prometería a mi nieto que te ayudaría? 📝 *`#{id}` - {texto} ({fecha})*.",
        "¡Ay! Qué me has pillado en el baño. Espera que voy a apuntarlo. (...) 📝 Vale, ya. *`#{id}` - {texto} ({fecha})*."
    ],
    "recordatorio_pasado_lista": [
        "👵🗂️ ¡Esto ya se te ha pasado! Más te vale que lo hayas hecho aunque no te lo haya recordado a tiempo.",
        "👵🗂️ Se te pasó el arroz con esto. A ver si prestamos más atención al calendario."
    ],

    # --- Configuración ---
    "configuracion_pide_nivel": [
        "👵⚙️ A ver, explícame tus manías. ¿Necesitas que te pregunte todo dos veces o eres de los que se lanzan sin pensar? Mi nivel actual es *{nivel}*. Elige uno nuevo (0-3).",
        "👵⚙️ Vamos a ajustar esto. Nivel actual: *{nivel}*. ¿Quieres que te trate con guantes de seda o que confíe en que no vas a romper nada? Dime, del 0 al 3."
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

    # --- Errores ---
    "error_formato": [
        "❗ ¡Así no, criatura! El formato es `fecha * texto`. ¡Concéntrate!",
        "❗ ¿Pero qué escribes? Tiene que ser `fecha * texto`. A veces pienso que te criaron los gnomos de jardín.",
        "❗ Te has equivocado con el formato del recordatorio: `fecha * texto`. No te preocupes, mi Neville que tanto se equivocaba llegó a ser una persona y mago maravilloso. ¿Te ha hablado de cuando derrotó al Señor Tenebroso? ¿No? Pues verás en la gran batalla de Hogwarts la mismísima espada de Griffindor se le apareció y... Ay bueno, que me lío. Quiero decir que si mi nieto pudo, tu también podrás.",
        "❗ Te has equivocado con el formato del recordatorio: `fecha * texto`. No te preocupes, mi Neville que tanto se equivocaba llegó a ser una persona y mago maravilloso. ¿Te ha hablado de cuando derrotó al Señor Tenebroso? ¿No? Bueno, pues ahora no puedo."
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
    ]
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