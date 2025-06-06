def handler(event, context):
    messsage = "Hello from Lambda!"
    print(messsage)
    return {
        'statusCode': 200,
        'body': messsage
    }
