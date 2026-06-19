-- Datos de ejemplo para la demo de PostgreSQL (se carga solo en el primer arranque).
-- Base: apcd  ·  Tabla: estudiantes

CREATE TABLE IF NOT EXISTS estudiantes (
    id        SERIAL PRIMARY KEY,
    nombre    TEXT        NOT NULL,
    carrera   TEXT        NOT NULL,
    semestre  INT,
    promedio  NUMERIC(3,1),
    creditos  INT,
    beca      BOOLEAN
);

INSERT INTO estudiantes (nombre, carrera, semestre, promedio, creditos, beca) VALUES
('Ana Restrepo',     'Ingenieria', 6, 8.9, 21, true),
('Luis Gomez',       'Medicina',   4, 7.4, 18, false),
('Sara Mendez',      'Derecho',    8, 9.2, 15, true),
('Diego Torres',     'Arte',       2, 6.8, 12, false),
('Marta Ruiz',       'Ingenieria', 7, 8.1, 24, false),
('Pablo Leon',       'Medicina',   5, 7.9, 18, true),
('Lucia Fernandez',  'Ingenieria', 3, 9.5, 21, true),
('Carlos Vega',      'Derecho',    6, 6.5, 15, false),
('Elena Castro',     'Medicina',   8, 8.7, 30, true),
('Mateo Rios',       'Arte',       4, 7.2, 12, false),
('Valentina Soto',   'Ingenieria', 5, 8.4, 21, false),
('Andres Mora',      'Derecho',    2, 5.9, 15, false),
('Camila Ortiz',     'Medicina',   7, 9.1, 24, true),
('Javier Pena',      'Arte',       6, 7.6, 18, false),
('Sofia Navarro',    'Ingenieria', 8, 9.8, 30, true),
('Daniel Cruz',      'Derecho',    4, 6.1, 12, false),
('Paula Gil',        'Medicina',   3, 8.3, 18, true),
('Hugo Marin',       'Ingenieria', 6, 7.0, 21, false),
('Laura Ramos',      'Arte',       5, 8.8, 15, true),
('Oscar Blanco',     'Derecho',    7, 7.5, 24, false),
('Irene Lozano',     'Medicina',   2, 6.9, 12, false),
('Tomas Aguilar',    'Ingenieria', 4, 9.0, 18, true),
('Nuria Sanz',       'Arte',       8, 8.2, 30, false),
('Adrian Cabrera',   'Derecho',    3, 7.8, 15, false),
('Clara Herrera',    'Medicina',   6, 9.4, 21, true),
('Raul Iglesias',    'Ingenieria', 5, 6.3, 18, false),
('Lola Vargas',      'Arte',       7, 7.7, 24, false),
('Marcos Duran',     'Derecho',    4, 8.6, 12, true),
('Alba Reyes',       'Medicina',   8, 7.1, 30, false),
('Bruno Santos',     'Ingenieria', 2, 8.0, 15, false);
