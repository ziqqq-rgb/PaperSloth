import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx' 
import './index.css'
import App from './app'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
    <div>Hello PaperSloth!</div>
  </React.StrictMode>,
)