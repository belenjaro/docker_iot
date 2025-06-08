USE agenda;

CREATE TABLE nodos (
    id VARCHAR(17) PRIMARY KEY,               
    servidor_mqtt VARCHAR(255) NOT NULL,      
    puerto INT NOT NULL,                      
    usuario VARCHAR(255),                     
    contrasena VARCHAR(255)                   
);