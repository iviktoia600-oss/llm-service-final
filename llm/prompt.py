SYSTEM = ("Составь краткое резюме пользовательского текста по-русски. "
          "Сохрани основные факты. Верни только резюме.")


def build(message, settings):
    return {"model": settings.model, "temperature": settings.temperature,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": message}]}
