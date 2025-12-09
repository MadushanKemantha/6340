from streamlit.web import bootstrap

def handler(request):
    # Set up environment for Streamlit
    import os
    os.environ['STREAMLIT_SERVER_PORT'] = '8080'
    os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
    
    # Run your Streamlit app
    bootstrap.run('grocery_app.py', '', [], {})
    
    return {
        'statusCode': 200,
        'body': 'Streamlit app running'
    }