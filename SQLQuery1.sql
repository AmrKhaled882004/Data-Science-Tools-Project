
USE DS_Tools_Project;


CREATE TABLE Books (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    Title NVARCHAR(255) NOT NULL,
	Price DECIMAL(10, 2),
    Rating INT,
    Availability INT,
    UPC NVARCHAR(255),
    ProductType NVARCHAR(255),
    PriceExclTax DECIMAL(10, 2),
    PriceInclTax DECIMAL(10, 2),
    Tax DECIMAL(10, 2),
    NumReviews INT,
    Description NVARCHAR(MAX)
	 
  
);



SELECT * FROM Books;





