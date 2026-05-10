client<llm> PolicyClient {
  provider google-ai
  options {
    model "gemini-2.5-flash"
    api_key env.GOOGLE_API_KEY
    temperature 0
  }
}
