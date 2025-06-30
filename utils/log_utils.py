def log_message(log_callback, message):
    """Логирует сообщение через callback или стандартный вывод"""
    if log_callback:
        log_callback(message)
    else:
        print(message)