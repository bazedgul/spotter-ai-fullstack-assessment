import '@testing-library/jest-dom'

Object.defineProperty(window.URL, 'createObjectURL', { writable: true, value: () => 'blob:mock' })
