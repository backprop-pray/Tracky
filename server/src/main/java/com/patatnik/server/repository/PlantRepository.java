package com.patatnik.server.repository;

import com.patatnik.server.model.Plant;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface PlantRepository extends JpaRepository<Plant, Long> {

    List<Plant> findByUserId(Long userId);

    List<Plant> findByUserIdOrderByCreatedAtDesc(Long userId);

    @Query("""
        SELECT p FROM Plant p
        LEFT JOIN FETCH p.processedPlant
        WHERE p.user.id = :userId
        ORDER BY p.createdAt DESC
    """)
    List<Plant> findByUserIdWithProcessedOrderByCreatedAtDesc(
        @Param("userId") Long userId
);
}
