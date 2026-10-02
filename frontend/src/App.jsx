import { useState, useEffect } from "react";
import './App.css'

function App() {
  const [check, setCheck] = useState(null);

  useEffect(() => {
      async function handleCheck() {
          try {
              const response = await fetch('http://localhost:8000/api/v1/')

              if (!response.ok) {
                  throw Error(response.statusText);
              }
              const data = await response.json();
              setCheck(data)
          } catch (error) {
              console.error(error)
          }
      }

      handleCheck();
  }, [])



  return (
    <>
        <h1>WorkBoard React</h1>
        <p>{ check?.status }</p>

    </>
  )
}

export default App
