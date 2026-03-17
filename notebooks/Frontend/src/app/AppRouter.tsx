import { Route, Routes } from 'react-router-dom'
import { InputPage } from '../pages/InputPage'
import { ComparePage } from '../pages/ComparePage'
import { routes } from '../config/routes'

export const AppRouter = () => (
  <Routes>
    <Route path={routes.input} element={<InputPage />} />
    <Route path="/compare/:jobId" element={<ComparePage />} />
  </Routes>
)

