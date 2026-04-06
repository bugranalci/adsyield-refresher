import { render, screen } from '@testing-library/react';
import App from './App';

test('renders ADSYIELD header', () => {
  render(<App />);
  const logo = screen.getByText(/ADSYIELD/i);
  expect(logo).toBeInTheDocument();
});
