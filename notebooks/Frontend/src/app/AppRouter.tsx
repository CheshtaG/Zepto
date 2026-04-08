import { Route, Routes } from 'react-router-dom'
import { Onboarding } from '../pages/Onboarding'
import { ComparePage } from '../pages/ComparePage'
import { routes } from '../config/routes'

export const AppRouter = () => (
  <Routes>
    <Route path={routes.input} element={<Onboarding />} />
    <Route path="/compare/:jobId" element={<ComparePage />} />
  </Routes>
)

