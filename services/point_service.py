from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from models import User, UserPoint, PointTransaction, PointAllocationType, UserRole

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class PointSummary:
    """Point summary for a user"""
    user_id: str
    current_points: int
    total_points: int
    total_used_points: int
    recent_transactions: int
    last_transaction_date: Optional[datetime] = None


@dataclass
class TransactionSummary:
    """Transaction summary for a user"""
    total_sent: int
    total_received: int
    points_sent: int
    points_received: int
    net_points: int
    recent_activity_days: int


class PointService:
    """
    Service for managing user points and transactions.
    Handles point allocation, deduction, and transaction history.
    """
    
    def __init__(self, db: Session):
        """
        Initialize PointService with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        logger.info("PointService initialized")

    def get_user_point_summary(self, user_id: str) -> Optional[PointSummary]:
        """
        Get comprehensive point summary for a user.
        
        Args:
            user_id: User ID to get points for
            
        Returns:
            PointSummary or None if user has no points
        """
        try:
            user_points = self.db.query(UserPoint).filter(UserPoint.user_id == user_id).first()
            
            if not user_points:
                return PointSummary(
                    user_id=user_id,
                    current_points=0,
                    total_points=0,
                    total_used_points=0,
                    recent_transactions=0
                )
            
            # Get recent transactions count (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_transactions = self.db.query(PointTransaction).filter(
                (PointTransaction.giver_id == user_id) | (PointTransaction.receiver_id == user_id),
                PointTransaction.created_at >= thirty_days_ago
            ).count()
            
            # Get last transaction date
            last_transaction = self.db.query(PointTransaction).filter(
                (PointTransaction.giver_id == user_id) | (PointTransaction.receiver_id == user_id)
            ).order_by(PointTransaction.created_at.desc()).first()
            
            last_transaction_date = last_transaction.created_at if last_transaction else None
            
            return PointSummary(
                user_id=user_id,
                current_points=user_points.current_points,
                total_points=user_points.total_points,
                total_used_points=user_points.total_used_points,
                recent_transactions=recent_transactions,
                last_transaction_date=last_transaction_date
            )
            
        except Exception as e:
            logger.error(f"Error getting point summary for user {user_id}: {str(e)}")
            raise

    def get_user_transaction_summary(self, user_id: str, days: int = 30) -> TransactionSummary:
        """
        Get transaction summary for a user over specified period.
        
        Args:
            user_id: User ID to get transactions for
            days: Number of days to look back
            
        Returns:
            TransactionSummary with transaction statistics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get sent transactions
            sent_transactions = self.db.query(PointTransaction).filter(
                PointTransaction.giver_id == user_id,
                PointTransaction.created_at >= cutoff_date
            ).all()
            
            # Get received transactions
            received_transactions = self.db.query(PointTransaction).filter(
                PointTransaction.receiver_id == user_id,
                PointTransaction.created_at >= cutoff_date
            ).all()
            
            # Calculate totals
            total_sent = len(sent_transactions)
            total_received = len(received_transactions)
            points_sent = sum(t.points for t in sent_transactions)
            points_received = sum(t.points for t in received_transactions)
            net_points = points_received - points_sent
            
            return TransactionSummary(
                total_sent=total_sent,
                total_received=total_received,
                points_sent=points_sent,
                points_received=points_received,
                net_points=net_points,
                recent_activity_days=days
            )
            
        except Exception as e:
            logger.error(f"Error getting transaction summary for user {user_id}: {str(e)}")
            raise

    def allocate_points(
        self, 
        receiver_id: str, 
        points: int, 
        allocation_type: PointAllocationType,
        giver_id: Optional[str] = None
    ) -> bool:
        """
        Allocate points to a user.
        
        Args:
            receiver_id: User ID to receive points
            points: Number of points to allocate
            allocation_type: Type of allocation
            giver_id: Optional giver user ID (for tracking)
            
        Returns:
            True if allocation was successful
        """
        try:
            logger.info(f"Allocating {points} points to user {receiver_id}")
            
            # Get or create user points record
            user_points = self.db.query(UserPoint).filter(UserPoint.user_id == receiver_id).first()
            
            if not user_points:
                # Get user email for the record
                user = self.db.query(User).filter(User.id == receiver_id).first()
                if not user:
                    logger.error(f"User not found: {receiver_id}")
                    return False
                
                user_points = UserPoint(
                    user_id=receiver_id,
                    user_email=user.email,
                    total_points=0,
                    current_points=0,
                    total_used_points=0
                )
                self.db.add(user_points)
            
            # Update points
            user_points.total_points += points
            user_points.current_points += points
            user_points.updated_at = datetime.utcnow()
            
            # Create transaction record
            transaction = PointTransaction(
                giver_id=giver_id,
                receiver_id=receiver_id,
                receiver_email=user_points.user_email,
                points=points,
                transaction_type=allocation_type.value,
                created_at=datetime.utcnow()
            )
            
            if giver_id:
                giver = self.db.query(User).filter(User.id == giver_id).first()
                if giver:
                    transaction.giver_email = giver.email
            
            self.db.add(transaction)
            self.db.commit()
            
            logger.info(f"Successfully allocated {points} points to user {receiver_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error allocating points: {str(e)}")
            raise

    def deduct_points(self, user_id: str, points: int, reason: str = "deduction") -> bool:
        """
        Deduct points from a user. Super users and admin users are exempt from point deductions.
        
        Args:
            user_id: User ID to deduct points from
            points: Number of points to deduct
            reason: Reason for deduction
            
        Returns:
            True if deduction was successful or user is exempt
        """
        try:
            # Check user role first
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User not found: {user_id}")
                return False
            
            # 🚫 NO POINT DEDUCTION for super_user and admin_user
            if user.role in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
                logger.info(f"🔓 Point deduction skipped for {user.role}: {user.email}")
                return True  # Return success without deducting points
            
            logger.info(f"Deducting {points} points from user {user_id}")
            
            user_points = self.db.query(UserPoint).filter(UserPoint.user_id == user_id).first()
            
            if not user_points or user_points.current_points < points:
                logger.warning(f"Insufficient points for user {user_id}")
                return False
            
            # Update points (only for general users)
            user_points.current_points -= points
            user_points.total_used_points += points
            user_points.updated_at = datetime.utcnow()
            
            # Create transaction record
            transaction = PointTransaction(
                giver_id=user_id,
                giver_email=user_points.user_email,
                points=points,
                transaction_type=reason,
                created_at=datetime.utcnow()
            )
            
            self.db.add(transaction)
            self.db.commit()
            
            logger.info(f"Successfully deducted {points} points from user {user_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deducting points: {str(e)}")
            raise

    def transfer_points(self, giver_id: str, receiver_id: str, points: int) -> bool:
        """
        Transfer points between users.
        
        Args:
            giver_id: User ID giving points
            receiver_id: User ID receiving points
            points: Number of points to transfer
            
        Returns:
            True if transfer was successful
        """
        try:
            logger.info(f"Transferring {points} points from {giver_id} to {receiver_id}")
            
            # Get giver points
            giver_points = self.db.query(UserPoint).filter(UserPoint.user_id == giver_id).first()
            if not giver_points or giver_points.current_points < points:
                logger.warning(f"Insufficient points for transfer from user {giver_id}")
                return False
            
            # Get or create receiver points
            receiver_points = self.db.query(UserPoint).filter(UserPoint.user_id == receiver_id).first()
            if not receiver_points:
                receiver = self.db.query(User).filter(User.id == receiver_id).first()
                if not receiver:
                    logger.error(f"Receiver user not found: {receiver_id}")
                    return False
                
                receiver_points = UserPoint(
                    user_id=receiver_id,
                    user_email=receiver.email,
                    total_points=0,
                    current_points=0,
                    total_used_points=0
                )
                self.db.add(receiver_points)
            
            # Update points
            giver_points.current_points -= points
            giver_points.total_used_points += points
            
            receiver_points.current_points += points
            receiver_points.total_points += points
            
            # Create transaction record
            transaction = PointTransaction(
                giver_id=giver_id,
                giver_email=giver_points.user_email,
                receiver_id=receiver_id,
                receiver_email=receiver_points.user_email,
                points=points,
                transaction_type="transfer",
                created_at=datetime.utcnow()
            )
            
            self.db.add(transaction)
            self.db.commit()
            
            logger.info(f"Successfully transferred {points} points from {giver_id} to {receiver_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error transferring points: {str(e)}")
            raise

    def get_user_transactions(
        self, 
        user_id: str, 
        limit: int = 50, 
        offset: int = 0,
        transaction_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get transaction history for a user.
        
        Args:
            user_id: User ID to get transactions for
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            transaction_type: Optional filter by transaction type
            
        Returns:
            List of transaction dictionaries
        """
        try:
            query = self.db.query(PointTransaction).filter(
                (PointTransaction.giver_id == user_id) | (PointTransaction.receiver_id == user_id)
            )
            
            if transaction_type:
                query = query.filter(PointTransaction.transaction_type == transaction_type)
            
            transactions = query.order_by(
                PointTransaction.created_at.desc()
            ).offset(offset).limit(limit).all()
            
            transaction_list = []
            for transaction in transactions:
                transaction_dict = {
                    "id": transaction.id,
                    "type": "sent" if transaction.giver_id == user_id else "received",
                    "points": transaction.points,
                    "transaction_type": transaction.transaction_type,
                    "created_at": transaction.created_at,
                    "giver_id": transaction.giver_id,
                    "giver_email": transaction.giver_email,
                    "receiver_id": transaction.receiver_id,
                    "receiver_email": transaction.receiver_email
                }
                transaction_list.append(transaction_dict)
            
            return transaction_list
            
        except Exception as e:
            logger.error(f"Error getting transactions for user {user_id}: {str(e)}")
            raise

    def calculate_user_activity_status(self, user_id: str, days: int = 7) -> str:
        """
        Calculate user activity status based on recent transactions.
        
        Args:
            user_id: User ID to check activity for
            days: Number of days to look back
            
        Returns:
            Activity status string ("Active" or "Inactive")
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            recent_activity = self.db.query(PointTransaction).filter(
                (PointTransaction.giver_id == user_id) | (PointTransaction.receiver_id == user_id),
                PointTransaction.created_at >= cutoff_date
            ).first()
            
            return "Active" if recent_activity else "Inactive"
            
        except Exception as e:
            logger.error(f"Error calculating activity status for user {user_id}: {str(e)}")
            return "Unknown"

    def get_point_statistics(self) -> Dict[str, Any]:
        """
        Get overall point statistics for the system.
        
        Returns:
            Dictionary with point statistics
        """
        try:
            # Total points in system
            total_points = self.db.query(
                self.db.func.coalesce(self.db.func.sum(UserPoint.total_points), 0)
            ).scalar()
            
            # Current points in circulation
            current_points = self.db.query(
                self.db.func.coalesce(self.db.func.sum(UserPoint.current_points), 0)
            ).scalar()
            
            # Total used points
            used_points = self.db.query(
                self.db.func.coalesce(self.db.func.sum(UserPoint.total_used_points), 0)
            ).scalar()
            
            # Number of users with points
            users_with_points = self.db.query(UserPoint).filter(UserPoint.current_points > 0).count()
            
            # Recent transactions (last 7 days)
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            recent_transactions = self.db.query(PointTransaction).filter(
                PointTransaction.created_at >= seven_days_ago
            ).count()
            
            return {
                "total_points_distributed": int(total_points),
                "current_points_available": int(current_points),
                "total_points_used": int(used_points),
                "users_with_points": users_with_points,
                "recent_transactions": recent_transactions
            }
            
        except Exception as e:
            logger.error(f"Error getting point statistics: {str(e)}")
            raise