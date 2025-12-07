import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import traceback
import sys
import io

# Setup Streamlit page configuration
st.set_page_config(
    page_title="ConceptViz",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar ---
st.sidebar.title("ConceptViz 🧠")
st.sidebar.markdown(
    """
    **ConceptViz** ayuda a visualizar conceptos complejos utilizando IA generativa.
    
    1. Ingresa tu **API Key de Gemini**.
    2. Escribe un concepto (ej: 'Ciclo de Carnot').
    3. Obtén una explicación y una gráfica interactiva.
    """
)

api_key = st.sidebar.text_input("Ingresa tu Gemini API Key", type="password")

if api_key:
    try:
        genai.configure(api_key=api_key)
        
        # Dynamically list available models that support generateContent
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except Exception as e:
            st.sidebar.error(f"Error listando modelos: {e}")
            
        # Default to a reasonable model if available, else first one
        default_index = 0
        preferred_models = ["models/gemini-1.5-flash", "models/gemini-pro"]
        for i, m_name in enumerate(available_models):
            if any(p in m_name for p in preferred_models):
                default_index = i
                break
        
        if available_models:
            selected_model_name = st.sidebar.selectbox("Selecciona el modelo", available_models, index=default_index)
            model = genai.GenerativeModel(selected_model_name)
            st.sidebar.success(f"Conectado a {selected_model_name}", icon="✅")
        else:
            st.sidebar.error("No se encontraron modelos disponibles para esta API Key.")
            
    except Exception as e:
        st.sidebar.error(f"Error al configurar API Key: {e}")
else:
    st.sidebar.warning("Por favor ingresa tu API Key para continuar.")

# --- Functions ---

def get_explanation(concept):
    """Generates a brief textual explanation of the concept."""
    try:
        prompt = f"""
        Explica el concepto '{concept}' de manera breve, didáctica y clara para un estudiante universitario. 
        Usa un tono educativo. Máximo 200 palabras.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generando explicación: {e}"

def get_visualization_code(concept, error_context=None):
    """Generates Python code to visualize the concept using Plotly."""
    
    base_prompt = f"""
    Genera un script de Python COMPLETO y EJECUTABLE para visualizar el concepto: '{concept}' usando la librería 'plotly'.
    
    Reglas ESTRICTAS:
    1. El código debe crear un objeto figura de Plotly y guardarlo en una variable llamada `fig`.
    2. NO uses `fig.show()`. La figura se renderizará externamente.
    3. Si necesitas datos, genéralos dinámicamente usando `numpy` (np) o `pandas` (pd).
    4. Usa librerías estándar o `plotly`, `pandas`, `numpy`.
    5. El código debe ser autocontenido. No asumas archivos externos.
    6. Asegúrate de manejar etiquetas, títulos y leyendas para que la gráfica sea educativa.
    7. IMPORTANTE: La app puede estar en modo CLARO u OSCURO. Por favor:
       - Usa `fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')` para fondo transparente.
       - Configura `height=700` en update_layout para que la gráfica se vea grande y clára.
       - Asegúrate que el texto y las líneas sean legibles en ambos fondos (o usa colores vibrantes).
    8. No incluyas bloques markdown (```python ... ```). Devuelve SOLAMENTE el código puro.
    
    Ejemplo de estructura esperada:
    import plotly.graph_objects as go
    import numpy as np
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    fig = go.Figure(data=go.Scatter(x=x, y=y))
    fig.update_layout(
        title='Seno de x',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=700,
        margin=dict(t=50, l=50, r=50, b=50)
    )
    """

    if error_context:
        prompt = f"""
        {base_prompt}
        
        INTENTO ANTERIOR FALLÓ CON ESTE ERROR:
        {error_context}
        
        Por favor corrige el código para solucionar el error.
        """
    else:
        prompt = base_prompt

    try:
        response = model.generate_content(prompt)
        # Clean specific markdown formatting if Gemini adds it despite instructions
        code = response.text
        code = code.replace("```python", "").replace("```", "").strip()
        return code
    except Exception as e:
        raise Exception(f"Error generando código: {e}")

def execute_and_render(code_str):
    """Executes the generated code and returns the fig object."""
    # Define a restricted local scope
    local_scope = {}
    
    # Pre-import allowed modules so the generated code uses them
    # Though the generated code usually imports them, providing them in scope/globals safeguards 
    # against some context issues, but exec usually handles imports inside the string fine.
    
    try:
        # Standard imports available for the script
        exec_globals = {
            "pd": pd,
            "np": np,
            "go": go,
            "px": px,
            "__builtins__": __builtins__ # In a real secure env, we'd limit this heavily.
        }
        
        exec(code_str, exec_globals, local_scope)
        
        if 'fig' in local_scope:
            return local_scope['fig']
        else:
            raise ValueError("El código ejecutado no generó una variable 'fig'.")
            
    except Exception as e:
        # Return the exception to be handled (and potentially used for retry)
        raise e

# --- Main UI ---

st.title("ConceptViz: Visualizador de Conceptos")
st.markdown("Explora conceptos complejos con explicaciones claras y gráficos interactivos.")

concept = st.text_input("Ingresa un concepto (ej: 'Distribución Normal', 'Onda Senoidal', 'Atractor de Lorenz')", "")

if st.button("Generar Visualización", type="primary"):
    if not concept:
        st.error("Por favor escribe un concepto.")
    elif not api_key:
        st.error("Por favor configura tu API Key en la barra lateral.")
    else:
        # Create tabs for organized view
        tab1, tab2 = st.tabs(["Explicación", "Visualización Interactiva"])
        
        with tab1:
            with st.spinner("Generando explicación..."):
                explanation = get_explanation(concept)
                st.markdown(explanation)
        
        with tab2:
            with st.spinner("Diseñando y programando visualización..."):
                # Retry logic
                max_retries = 3
                attempt = 0
                success = False
                last_error = None
                code_to_run = ""
                
                status_placeholder = st.empty()
                
                while attempt < max_retries and not success:
                    try:
                        status_placeholder.info(f"Intento {attempt + 1}/{max_retries} generando código...")
                        code_to_run = get_visualization_code(concept, error_context=last_error)
                        
                        # Show code in expander for transparency/debugging
                        with st.expander(f"Ver código generado (Intento {attempt + 1})"):
                            st.code(code_to_run, language='python')
                        
                        fig = execute_and_render(code_to_run)
                        st.plotly_chart(fig, use_container_width=True)
                        success = True
                        status_placeholder.success("¡Visualización generada con éxito!")
                        
                    except Exception as e:
                        last_error = str(e)
                        # traceback_str = traceback.format_exc() # detailed trace
                        # last_error += f"\nDetailed Trace: {traceback_str}"
                        st.warning(f"Intento {attempt + 1} falló: {e}")
                        attempt += 1
                
                if not success:
                    st.error("No se pudo generar la visualización después de varios intentos.")
                    st.error(f"Último error: {last_error}")
