from typing import Any, Dict, List, Optional, Union

class ResponseHandler:
    @staticmethod
    def success(
        data: Union[List, Dict, Any] = None,
        type: str = "text",
        message: str = "Operation successful"
    ) -> Dict:
        """
        Create a success response
        
        Args:
            data: Response data (list, dict, or any other type)
            type: Response type ('text' or 'excel')
            message: Success message
            
        Returns:
            Dict containing standardized success response
        """
        if data is None:
            data = []
            
        return {
            "success": True,
            "data": data,
            "type": type,
            "error": None,
            "message": message
        }
    
    @staticmethod
    def error(
        error: str = "Internal Server Error",
        message: str = "Operation failed"
    ) -> Dict:
        """
        Create an error response
        
        Args:
            error: Error details
            message: Error message
            
        Returns:
            Dict containing standardized error response
        """
        return {
            "success": False,
            "data": [],
            "type": "text",
            "error": error,
            "message": message
        }
